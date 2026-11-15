"""
Baby-Step Giant-Step (BSGS) Discrete Logarithm Representation & Solver
Implements the algebraic time-memory trade-off on the secp256k1 group (E(F_p), +).
Solves P_target = k * G for k in [L, R] where P_target is an elliptic curve group element.
Tracks explicit resource accounting:
- Reusable setup (baby-step table {j * G})
- Per-instance setup (L * G, Q = P_target - L * G, M = m * G)
- Online search (giant steps Q_i = Q_{i-1} - M and hash table probes)
- Memory footprint and fine-grained group operation counts
"""
import math
import time
from dataclasses import dataclass, field
from typing import Tuple, Optional, Dict, Any

from puzzle_solver.verification.secp256k1 import (
    P, GX, GY, scalar_mult, jacobian_add_affine, jacobian_add, to_affine
)

@dataclass
class GroupOpCounters:
    jacobian_doubles: int = 0
    jacobian_adds: int = 0
    affine_conversions: int = 0

    def total(self) -> int:
        return self.jacobian_doubles + self.jacobian_adds + self.affine_conversions

    def to_dict(self) -> Dict[str, int]:
        return {
            "jacobian_doubles": self.jacobian_doubles,
            "jacobian_adds": self.jacobian_adds,
            "affine_conversions": self.affine_conversions,
            "total_ops": self.total()
        }

@dataclass
class BabyStepTable:
    """Precomputed table of {j * G : 0 <= j < m}."""
    m: int
    table: Dict[Optional[Tuple[int, int]], int] # maps affine (x, y) or None (infinity) -> j
    setup_seconds: float
    op_counts: GroupOpCounters

    @classmethod
    def build(cls, m: int) -> 'BabyStepTable':
        t0 = time.perf_counter()
        ops = GroupOpCounters()
        table: Dict[Optional[Tuple[int, int]], int] = {None: 0} # 0 * G = infinity
        
        if m > 1:
            G_aff = (GX, GY)
            table[G_aff] = 1
            cur_jac = (GX, GY, 1)
            for j in range(2, m):
                cur_jac = jacobian_add_affine(cur_jac, G_aff)
                ops.jacobian_adds += 1
                cur_aff = to_affine(cur_jac)
                ops.affine_conversions += 1
                table[cur_aff] = j
                
        elapsed = time.perf_counter() - t0
        return cls(m=m, table=table, setup_seconds=elapsed, op_counts=ops)

@dataclass(frozen=True)
class BSGSResult:
    success: bool
    recovered_key: Optional[int]
    L: int
    R: int
    N: int
    m: int
    t_baby: float
    t_instance: float
    t_online: float
    t_cold: float
    t_warm: float
    baby_entries: int
    giant_steps: int
    table_probes: int
    group_ops_baby: Dict[str, int]
    group_ops_instance: Dict[str, int]
    group_ops_online: Dict[str, int]
    group_ops_total: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "recovered_key": self.recovered_key,
            "recovered_key_hex": hex(self.recovered_key) if self.recovered_key is not None else None,
            "L": self.L,
            "R": self.R,
            "N": self.N,
            "m": self.m,
            "t_baby_seconds": round(self.t_baby, 6),
            "t_instance_seconds": round(self.t_instance, 6),
            "t_online_seconds": round(self.t_online, 6),
            "t_cold_seconds": round(self.t_cold, 6),
            "t_warm_seconds": round(self.t_warm, 6),
            "baby_entries": self.baby_entries,
            "giant_steps": self.giant_steps,
            "table_probes": self.table_probes,
            "group_ops_baby": self.group_ops_baby,
            "group_ops_instance": self.group_ops_instance,
            "group_ops_online": self.group_ops_online,
            "group_ops_total": self.group_ops_total
        }

class BSGSSolver:
    """
    Solves discrete logarithm P_target = k * G for k in [L, R].
    Strictly requires an elliptic-curve point P_target.
    """
    def __init__(self, precomputed_baby_table: Optional[BabyStepTable] = None):
        self.cached_baby_table = precomputed_baby_table

    def solve(
        self,
        L: int,
        R: int,
        P_target: Tuple[int, int],
        baby_table: Optional[BabyStepTable] = None
    ) -> BSGSResult:
        N = R - L + 1
        m = math.isqrt(N) + 1
        
        # 1. Reusable Baby-Step Setup
        if baby_table is not None and baby_table.m >= m:
            bt = baby_table
            t_baby = 0.0 # Reused, charged as 0 in warm execution
            ops_baby = GroupOpCounters()
        elif self.cached_baby_table is not None and self.cached_baby_table.m >= m:
            bt = self.cached_baby_table
            t_baby = 0.0
            ops_baby = GroupOpCounters()
        else:
            bt = BabyStepTable.build(m)
            t_baby = bt.setup_seconds
            ops_baby = bt.op_counts

        # 2. Per-Instance Setup
        t_inst_start = time.perf_counter()
        ops_inst = GroupOpCounters()

        # Compute L * G
        L_aff = scalar_mult(L)
        if L_aff is None:
            # L is multiple of curve order
            neg_L_aff = None
        else:
            neg_L_aff = (L_aff[0], (-L_aff[1]) % P)

        # Compute Q = P_target - L * G
        if neg_L_aff is None:
            Q = P_target
        elif P_target == L_aff:
            Q = None # point at infinity
        else:
            # point addition
            p1_jac = (P_target[0], P_target[1], 1)
            p2_jac = (neg_L_aff[0], neg_L_aff[1], 1)
            sum_jac = jacobian_add(p1_jac, p2_jac)
            ops_inst.jacobian_adds += 1
            Q = to_affine(sum_jac)
            ops_inst.affine_conversions += 1

        # Giant-step step point: M = m * G, and -M
        M_aff = scalar_mult(m)
        neg_M_aff = (M_aff[0], (-M_aff[1]) % P)
        
        t_inst = time.perf_counter() - t_inst_start

        # 3. Online Giant-Step Search
        t_online_start = time.perf_counter()
        ops_online = GroupOpCounters()
        
        cur_Q = Q
        giant_steps = 0
        table_probes = 0
        found_k = None
        max_i = math.ceil(N / m)

        for i in range(max_i + 1):
            giant_steps += 1
            table_probes += 1
            key = None if cur_Q is None else (cur_Q[0], cur_Q[1])
            
            if key in bt.table:
                j = bt.table[key]
                candidate_k = L + i * m + j
                if L <= candidate_k <= R:
                    # Verify candidate
                    cand_aff = scalar_mult(candidate_k)
                    if cand_aff == P_target:
                        found_k = candidate_k
                        break

            # Advance to next giant step: Q_{i+1} = Q_i - M
            if cur_Q is None:
                cur_Q = neg_M_aff
            else:
                cur_jac = jacobian_add_affine((cur_Q[0], cur_Q[1], 1), neg_M_aff)
                ops_online.jacobian_adds += 1
                cur_Q = to_affine(cur_jac)
                ops_online.affine_conversions += 1

        t_online = time.perf_counter() - t_online_start
        t_cold = bt.setup_seconds + t_inst + t_online
        t_warm = t_inst + t_online

        total_ops = GroupOpCounters(
            jacobian_doubles=ops_baby.jacobian_doubles + ops_inst.jacobian_doubles + ops_online.jacobian_doubles,
            jacobian_adds=ops_baby.jacobian_adds + ops_inst.jacobian_adds + ops_online.jacobian_adds,
            affine_conversions=ops_baby.affine_conversions + ops_inst.affine_conversions + ops_online.affine_conversions
        )

        return BSGSResult(
            success=(found_k is not None),
            recovered_key=found_k,
            L=L,
            R=R,
            N=N,
            m=m,
            t_baby=bt.setup_seconds,
            t_instance=t_inst,
            t_online=t_online,
            t_cold=t_cold,
            t_warm=t_warm,
            baby_entries=len(bt.table),
            giant_steps=giant_steps,
            table_probes=table_probes,
            group_ops_baby=ops_baby.to_dict(),
            group_ops_instance=ops_inst.to_dict(),
            group_ops_online=ops_online.to_dict(),
            group_ops_total=total_ops.to_dict()
        )

@dataclass(frozen=True)
class LinearDlogResult:
    success: bool
    recovered_key: Optional[int]
    candidates_tested: int
    wall_clock_seconds: float
    keys_per_second: float
    group_ops: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "recovered_key": self.recovered_key,
            "candidates_tested": self.candidates_tested,
            "wall_clock_seconds": round(self.wall_clock_seconds, 6),
            "keys_per_second": round(self.keys_per_second, 2),
            "group_ops": self.group_ops
        }

class LinearDlogScanner:
    """
    Reference linear stepping solver for exact comparison against BSGS on P_target = k * G.
    Uses the exact same mixed Jacobian point addition stepping as SequentialScanner.
    """
    @staticmethod
    def solve(L: int, R: int, P_target: Tuple[int, int]) -> LinearDlogResult:
        t0 = time.perf_counter()
        ops = GroupOpCounters()
        G_affine = (GX, GY)
        
        # Test first candidate (k = L)
        first_aff = scalar_mult(L)
        if first_aff is None:
            raise ValueError("L evaluates to point at infinity")
            
        cur_jac = (first_aff[0], first_aff[1], 1)
        cur_aff = first_aff
        tested = 1

        if cur_aff == P_target:
            elapsed = time.perf_counter() - t0
            return LinearDlogResult(
                success=True,
                recovered_key=L,
                candidates_tested=1,
                wall_clock_seconds=elapsed,
                keys_per_second=1.0 / max(elapsed, 1e-9),
                group_ops=ops.to_dict()
            )

        for k in range(L + 1, R + 1):
            cur_jac = jacobian_add_affine(cur_jac, G_affine)
            ops.jacobian_adds += 1
            cur_aff = to_affine(cur_jac)
            ops.affine_conversions += 1
            tested += 1

            if cur_aff == P_target:
                elapsed = time.perf_counter() - t0
                return LinearDlogResult(
                    success=True,
                    recovered_key=k,
                    candidates_tested=tested,
                    wall_clock_seconds=elapsed,
                    keys_per_second=tested / max(elapsed, 1e-9),
                    group_ops=ops.to_dict()
                )

        elapsed = time.perf_counter() - t0
        return LinearDlogResult(
            success=False,
            recovered_key=None,
            candidates_tested=tested,
            wall_clock_seconds=elapsed,
            keys_per_second=tested / max(elapsed, 1e-9),
            group_ops=ops.to_dict()
        )
