"""
Pollard's Kangaroo (Lambda) Algorithm Baseline for Bounded secp256k1 DLP
Implements the memory-efficient O(sqrt(N)) time, O(1) memory collision baseline.
Serves as the external memory/time frontier control branch.
Solves P_target = k * G for k in [L, R] using pseudo-random jump coalescing.
"""
import math
import time
from dataclasses import dataclass
from typing import Tuple, Optional, Dict, Any

from puzzle_solver.verification.secp256k1 import (
    P, ORDER, GX, GY, scalar_mult, jacobian_add, jacobian_add_affine, to_affine
)
from puzzle_solver.representations.bsgs import GroupOpCounters

@dataclass(frozen=True)
class KangarooResult:
    success: bool
    recovered_key: Optional[int]
    L: int
    R: int
    N: int
    t_tame: float
    t_wild: float
    t_total: float
    tame_steps: int
    wild_steps: int
    total_group_ops: int
    distinguished_points_stored: int
    group_ops: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "recovered_key": self.recovered_key,
            "recovered_key_hex": hex(self.recovered_key) if self.recovered_key is not None else None,
            "L": self.L,
            "R": self.R,
            "N": self.N,
            "t_tame_seconds": round(self.t_tame, 6),
            "t_wild_seconds": round(self.t_wild, 6),
            "t_total_seconds": round(self.t_total, 6),
            "tame_steps": self.tame_steps,
            "wild_steps": self.wild_steps,
            "total_steps": self.tame_steps + self.wild_steps,
            "total_group_ops": self.total_group_ops,
            "distinguished_points_stored": self.distinguished_points_stored,
            "group_ops": self.group_ops
        }

class PollardLambdaScanner:
    """
    Pollard Kangaroo algorithm on bounded interval [L, R].
    Uses 16 precomputed jump points for fast mixed Jacobian additions.
    Uses distinguished points (x mod 2^d == 0) to detect path coalescence in O(1) memory.
    Calibrated with mean jump mu ~ 0.5 * sqrt(N) and d ~ log2(mu / 4).
    """
    def __init__(self, num_jumps: int = 16):
        self.num_jumps = num_jumps

    def solve(
        self,
        L: int,
        R: int,
        P_target: Tuple[int, int],
        max_retries: int = 2
    ) -> KangarooResult:
        N = R - L + 1
        t0 = time.perf_counter()
        ops = GroupOpCounters()

        sqrt_N = max(4, math.isqrt(N))
        mu = max(2, sqrt_N // 2)

        # Generate jumps uniformly distributed in [1, 2*mu - 1] with mean exactly mu
        r = self.num_jumps
        jumps = [max(1, int(round(1 + (2 * mu - 2) * i / (r - 1)))) for i in range(r)]
        if all(s % 2 == 0 for s in jumps):
            jumps[0] = 1
        mu_act = sum(jumps) / len(jumps)

        # Distinguished point bitmask: expect ~ 16-32 DPs
        d = max(1, min(20, int(math.log2(max(2, mu // 4)))))
        dp_mask = (1 << d) - 1

        scaled_points_affine = [scalar_mult(s) for s in jumps]

        t_tame_total = 0.0
        t_wild_total = 0.0
        total_tame_steps = 0
        total_wild_steps = 0
        found_k = None
        dp_table: Dict[int, Tuple[int, int]] = {}

        for attempt in range(max_retries + 1):
            # -------------------------------------------------------------
            # Tame Kangaroo Walk
            # -------------------------------------------------------------
            t_tame_start = time.perf_counter()
            # Stagger tame start if retrying
            tame_dist = R + attempt * mu
            tame_aff = scalar_mult(tame_dist)
            tame_jac = (tame_aff[0], tame_aff[1], 1)
            
            # Max tame steps ~ 3.8 * sqrt(N)
            max_tame_steps = int(3.8 * sqrt_N) + 16

            for _ in range(max_tame_steps):
                total_tame_steps += 1
                aff = to_affine(tame_jac)
                ops.affine_conversions += 1
                
                if (aff[0] & dp_mask) == 0:
                    dp_table[aff[0]] = (tame_dist, aff[1])

                j_idx = aff[0] % len(jumps)
                jump_s = jumps[j_idx]
                jump_P = scaled_points_affine[j_idx]
                
                tame_dist += jump_s
                tame_jac = jacobian_add_affine(tame_jac, jump_P)
                ops.jacobian_adds += 1

            final_tame_aff = to_affine(tame_jac)
            dp_table[final_tame_aff[0]] = (tame_dist, final_tame_aff[1])
            t_tame_total += (time.perf_counter() - t_tame_start)

            # -------------------------------------------------------------
            # Wild Kangaroo Walk
            # -------------------------------------------------------------
            t_wild_start = time.perf_counter()
            wild_dist = 0
            wild_jac = (P_target[0], P_target[1], 1)
            max_wild_steps = int((tame_dist - L) // mu_act) + 32

            for _ in range(max_wild_steps):
                total_wild_steps += 1
                aff = to_affine(wild_jac)
                ops.affine_conversions += 1

                if aff[0] in dp_table:
                    t_d, t_y = dp_table[aff[0]]
                    if aff[1] == t_y:
                        candidate_k = t_d - wild_dist
                        if L <= candidate_k <= R:
                            if scalar_mult(candidate_k) == P_target:
                                found_k = candidate_k
                                break

                if wild_dist > (tame_dist - L + 2 * mu_act):
                    break

                j_idx = aff[0] % len(jumps)
                jump_s = jumps[j_idx]
                jump_P = scaled_points_affine[j_idx]

                wild_dist += jump_s
                wild_jac = jacobian_add_affine(wild_jac, jump_P)
                ops.jacobian_adds += 1

            t_wild_total += (time.perf_counter() - t_wild_start)
            if found_k is not None:
                break

        t_total = time.perf_counter() - t0

        return KangarooResult(
            success=(found_k is not None),
            recovered_key=found_k,
            L=L,
            R=R,
            N=N,
            t_tame=t_tame_total,
            t_wild=t_wild_total,
            t_total=t_total,
            tame_steps=total_tame_steps,
            wild_steps=total_wild_steps,
            total_group_ops=ops.total(),
            distinguished_points_stored=len(dp_table),
            group_ops=ops.to_dict()
        )
