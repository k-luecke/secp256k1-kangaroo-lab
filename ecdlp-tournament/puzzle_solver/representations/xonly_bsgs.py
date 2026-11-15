"""
X-Only Negation-Quotient BSGS Discrete Logarithm Representation & Solver
Implements coordinate elimination of the sign / y-coordinate via the negation automorphism
iota(P) = -P on the elliptic curve group (E(F_p), +).
Solves P_target = k * G for k in [L, R] using:
- x(Q_i) = x(P_j) <=> Q - i * W * G = +/- (j * G)
- Step size m_b = ceil(sqrt(N) / 2), giant step width W = 2 * m_b + 1
- Table size is approximately sqrt(N) / 2 (~50% memory and baby-step precomputation reduction vs standard BSGS)
- Sign is resolved exactly via O(1) integer comparison on y-coordinate upon x-match.
"""
import math
import time
from dataclasses import dataclass
from typing import Tuple, Optional, Dict, Any

from puzzle_solver.verification.secp256k1 import (
    P, GX, GY, scalar_mult, jacobian_add_affine, jacobian_add, to_affine
)
from puzzle_solver.representations.bsgs import GroupOpCounters

@dataclass
class XOnlyBabyStepTable:
    """Precomputed table of {x(j * G) -> (j, y(j * G)) : 0 <= j <= m_b}."""
    m_b: int
    W: int
    table: Dict[Optional[int], Tuple[int, int]] # maps x_coord or None (infinity) -> (j, y_coord)
    setup_seconds: float
    op_counts: GroupOpCounters

    @classmethod
    def build(cls, m_b: int) -> 'XOnlyBabyStepTable':
        t0 = time.perf_counter()
        ops = GroupOpCounters()
        W = 2 * m_b + 1
        table: Dict[Optional[int], Tuple[int, int]] = {None: (0, 0)} # 0 * G = infinity
        
        if m_b >= 1:
            G_aff = (GX, GY)
            table[G_aff[0]] = (1, G_aff[1])
            cur_jac = (GX, GY, 1)
            for j in range(2, m_b + 1):
                cur_jac = jacobian_add_affine(cur_jac, G_aff)
                ops.jacobian_adds += 1
                cur_aff = to_affine(cur_jac)
                ops.affine_conversions += 1
                table[cur_aff[0]] = (j, cur_aff[1])
                
        elapsed = time.perf_counter() - t0
        return cls(m_b=m_b, W=W, table=table, setup_seconds=elapsed, op_counts=ops)

@dataclass(frozen=True)
class XOnlyBSGSResult:
    success: bool
    recovered_key: Optional[int]
    L: int
    R: int
    N: int
    m_b: int
    W: int
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
            "m_b": self.m_b,
            "W": self.W,
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

class XOnlyBSGSSolver:
    """
    Solves discrete logarithm P_target = k * G for k in [L, R] using
    negation-quotient x-only matching.
    """
    def __init__(self, precomputed_table: Optional[XOnlyBabyStepTable] = None):
        self.cached_table = precomputed_table

    def solve(
        self,
        L: int,
        R: int,
        P_target: Tuple[int, int],
        baby_table: Optional[XOnlyBabyStepTable] = None
    ) -> XOnlyBSGSResult:
        N = R - L + 1
        m_b = max(1, math.ceil(math.isqrt(N) / 2))
        W = 2 * m_b + 1

        # 1. Reusable Baby-Step Setup
        if baby_table is not None and baby_table.m_b >= m_b:
            bt = baby_table
            t_baby = 0.0
            ops_baby = GroupOpCounters()
        elif self.cached_table is not None and self.cached_table.m_b >= m_b:
            bt = self.cached_table
            t_baby = 0.0
            ops_baby = GroupOpCounters()
        else:
            bt = XOnlyBabyStepTable.build(m_b)
            t_baby = bt.setup_seconds
            ops_baby = bt.op_counts

        # 2. Per-Instance Setup
        t_inst_start = time.perf_counter()
        ops_inst = GroupOpCounters()

        # Compute L * G
        L_aff = scalar_mult(L)
        if L_aff is None:
            neg_L_aff = None
        else:
            neg_L_aff = (L_aff[0], (-L_aff[1]) % P)

        # Compute Q = P_target - L * G
        if neg_L_aff is None:
            Q = P_target
        elif P_target == L_aff:
            Q = None # point at infinity
        else:
            p1_jac = (P_target[0], P_target[1], 1)
            p2_jac = (neg_L_aff[0], neg_L_aff[1], 1)
            sum_jac = jacobian_add(p1_jac, p2_jac)
            ops_inst.jacobian_adds += 1
            Q = to_affine(sum_jac)
            ops_inst.affine_conversions += 1

        # Giant-step step point: M = W * G, and -M
        M_aff = scalar_mult(W)
        neg_M_aff = (M_aff[0], (-M_aff[1]) % P)
        
        t_inst = time.perf_counter() - t_inst_start

        # 3. Online Giant-Step Search
        t_online_start = time.perf_counter()
        ops_online = GroupOpCounters()
        
        cur_Q = Q
        giant_steps = 0
        table_probes = 0
        found_k = None
        max_i = math.ceil(N / W) + 1

        for i in range(max_i + 1):
            giant_steps += 1
            table_probes += 1
            x_key = None if cur_Q is None else cur_Q[0]
            
            if x_key in bt.table:
                j, y_j = bt.table[x_key]
                if cur_Q is None:
                    candidate_k = L + i * W
                    if L <= candidate_k <= R:
                        found_k = candidate_k
                        break
                else:
                    y_i = cur_Q[1]
                    if y_i == y_j:
                        candidate_k = L + i * W + j
                        if L <= candidate_k <= R:
                            found_k = candidate_k
                            break
                    elif y_i == (-y_j) % P:
                        candidate_k = L + i * W - j
                        if L <= candidate_k <= R:
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

        return XOnlyBSGSResult(
            success=(found_k is not None),
            recovered_key=found_k,
            L=L,
            R=R,
            N=N,
            m_b=m_b,
            W=W,
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
