"""
Sequential Scanner Baseline
Implements explicit bounded enumeration of private keys using mixed Jacobian point addition (P + G)
and target Hash160 comparison.
Strict quarantine: Consumes ONLY public PuzzleSpec (no answer leakage).
"""
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable
from puzzle_solver.specs.schema import PuzzleSpec
from puzzle_solver.verification.secp256k1 import (
    scalar_mult, jacobian_add_affine, to_affine, GX, GY
)
from puzzle_solver.verification.address import (
    hash160, address_to_hash160, privkey_to_address
)

@dataclass(frozen=True)
class ScanResult:
    puzzle_id: str
    success: bool
    recovered_key_int: Optional[int]
    recovered_key_hex: Optional[str]
    recovered_address: Optional[str]
    candidates_tested: int
    total_space_size: int
    wall_clock_seconds: float
    keys_per_second: float
    target_address: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "puzzle_id": self.puzzle_id,
            "success": self.success,
            "recovered_key_int": self.recovered_key_int,
            "recovered_key_hex": self.recovered_key_hex,
            "recovered_address": self.recovered_address,
            "candidates_tested": self.candidates_tested,
            "total_space_size": self.total_space_size,
            "wall_clock_seconds": round(self.wall_clock_seconds, 6),
            "keys_per_second": round(self.keys_per_second, 2),
            "target_address": self.target_address
        }

class SequentialScanner:
    """
    Linear sequential scan over candidate_space [lower_bound, upper_bound].
    Uses mixed Jacobian stepping (P_{k+1} = P_k + G) and 20-byte Hash160 comparison
    to avoid full scalar multiplications and Base58 string formatting per non-matching candidate.
    """
    def __init__(self, spec: PuzzleSpec):
        self.spec = spec
        self.target_address = spec.target.target_value
        self.is_compressed = "compressed" in spec.target.target_type.lower()
        self.target_h160 = address_to_hash160(self.target_address)
        self.lower = spec.candidate_space.lower_bound
        self.upper = spec.candidate_space.upper_bound
        self.space_size = self.upper - self.lower + 1

    def run(self, progress_callback: Optional[Callable[[int, int, float], None]] = None) -> ScanResult:
        """
        Execute bounded linear search.
        progress_callback signature: (tested_count, total_space, elapsed_seconds)
        """
        start_time = time.perf_counter()
        G_affine = (GX, GY)
        
        # Initial point computation via full scalar multiplication
        first_aff = scalar_mult(self.lower)
        if first_aff is None:
            raise ValueError(f"Lower bound {self.lower} evaluates to point at infinity")
        
        # Test first candidate (k = lower)
        cur_jac = (first_aff[0], first_aff[1], 1)
        cur_aff = first_aff
        prefix = b'\x02' if (cur_aff[1] % 2 == 0) else b'\x03'
        pub = prefix + cur_aff[0].to_bytes(32, 'big')
        h160 = hash160(pub)
        
        candidates_tested = 1
        if h160 == self.target_h160:
            elapsed = time.perf_counter() - start_time
            recovered_addr = privkey_to_address(self.lower, compressed=self.is_compressed)
            return ScanResult(
                puzzle_id=self.spec.puzzle_id,
                success=True,
                recovered_key_int=self.lower,
                recovered_key_hex=hex(self.lower),
                recovered_address=recovered_addr,
                candidates_tested=1,
                total_space_size=self.space_size,
                wall_clock_seconds=elapsed,
                keys_per_second=1.0 / max(elapsed, 1e-9),
                target_address=self.target_address
            )

        # Iterate over remaining keys in [lower + 1, upper]
        for k in range(self.lower + 1, self.upper + 1):
            cur_jac = jacobian_add_affine(cur_jac, G_affine)
            cur_aff = to_affine(cur_jac)
            if cur_aff is None:
                continue
                
            prefix = b'\x02' if (cur_aff[1] % 2 == 0) else b'\x03'
            pub = prefix + cur_aff[0].to_bytes(32, 'big')
            h160 = hash160(pub)
            candidates_tested += 1

            if h160 == self.target_h160:
                elapsed = time.perf_counter() - start_time
                recovered_addr = privkey_to_address(k, compressed=self.is_compressed)
                return ScanResult(
                    puzzle_id=self.spec.puzzle_id,
                    success=True,
                    recovered_key_int=k,
                    recovered_key_hex=hex(k),
                    recovered_address=recovered_addr,
                    candidates_tested=candidates_tested,
                    total_space_size=self.space_size,
                    wall_clock_seconds=elapsed,
                    keys_per_second=candidates_tested / max(elapsed, 1e-9),
                    target_address=self.target_address
                )

            if progress_callback and (candidates_tested % 1000 == 0):
                progress_callback(candidates_tested, self.space_size, time.perf_counter() - start_time)

        elapsed = time.perf_counter() - start_time
        return ScanResult(
            puzzle_id=self.spec.puzzle_id,
            success=False,
            recovered_key_int=None,
            recovered_key_hex=None,
            recovered_address=None,
            candidates_tested=candidates_tested,
            total_space_size=self.space_size,
            wall_clock_seconds=elapsed,
            keys_per_second=candidates_tested / max(elapsed, 1e-9),
            target_address=self.target_address
        )
