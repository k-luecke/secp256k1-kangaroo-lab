"""
Dual-End Projective Differential BSGS Solver for secp256k1 Bounded DLP
Discovery Cycle 4: Bilateral Y-Coordinate Elimination & Optimal Asymmetric Ratio

Implements:
1. Pure 1D projective (X : Z) differential baby-step table construction using Brier-Joye recurrence
   with Montgomery batch inversion. (Zero modular inversions during stepping, 1 inversion total).
   Eliminates all Y-coordinates from stored dictionary ({x_coord -> j}).
2. Pure 1D projective (X : Z) differential giant-step stepping with Montgomery batch inversion.
3. Optimal asymmetric step ratio:
     m_b^* = floor(sqrt(N / 2))
     W^* = 2 * m_b^* + 1 ~= sqrt(2N)
     m_g^* = ceil(N / W^*) ~= floor(sqrt(N / 2))
     Total steps across both phases = sqrt(2N) ~= 1.414 * sqrt(N) (theoretical minimum).
"""
import math
import time
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Any, List

from puzzle_solver.verification.secp256k1 import (
    P, B, GX, GY, scalar_mult, jacobian_add, jacobian_add_affine, to_affine
)
from puzzle_solver.representations.bsgs import GroupOpCounters
from puzzle_solver.representations.diff_xonly_bsgs import montgomery_batch_invert

@dataclass
class DualDiffBabyTable:
    """Precomputed table of {x(j * G) -> j : 1 <= j <= m_b} without Y-coordinates."""
    m_b: int
    W: int
    table: Dict[int, int]
    setup_seconds: float
    op_counts: GroupOpCounters

    @classmethod
    def build(cls, m_b: int) -> 'DualDiffBabyTable':
        t0 = time.perf_counter()
        ops = GroupOpCounters()
        W = 2 * m_b + 1
        table: Dict[int, int] = {}

        if m_b >= 1:
            table[GX] = 1
        if m_b >= 2:
            G2_aff = scalar_mult(2)
            table[G2_aff[0]] = 2
            ops.jacobian_adds += 1

        if m_b >= 3:
            X_prev, Z_prev = GX, 1
            X_curr, Z_curr = G2_aff[0], 1
            xs = GX
            b_const_4 = (4 * B) % P

            proj_X = []
            proj_Z = []
            indices = []

            for j in range(3, m_b + 1):
                xs_Z = (xs * Z_curr) % P
                T1 = (X_curr - xs_Z) % P
                T1_sq = (T1 * T1) % P
                Z_next = (T1_sq * Z_prev) % P

                Z_curr_sq = (Z_curr * Z_curr) % P
                term1 = (2 * X_curr * xs * (X_curr + xs_Z)) % P
                term2 = (b_const_4 * Z_curr_sq) % P
                T2 = (term1 + term2) % P
                X_next = (T2 * Z_prev - X_prev * T1_sq) % P

                proj_X.append(X_next)
                proj_Z.append(Z_next)
                indices.append(j)

                X_prev, Z_prev = X_curr, Z_curr
                X_curr, Z_curr = X_next, Z_next
                ops.jacobian_adds += 1

            inv_Z = montgomery_batch_invert(proj_Z)
            ops.affine_conversions += 1 # 1 batch inversion

            for idx, j_val in enumerate(indices):
                x_aff = (proj_X[idx] * inv_Z[idx]) % P
                table[x_aff] = j_val

        elapsed = time.perf_counter() - t0
        return cls(m_b=m_b, W=W, table=table, setup_seconds=elapsed, op_counts=ops)

@dataclass(frozen=True)
class DualDiffResult:
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
    baby_steps: int
    giant_steps: int
    total_steps: int
    total_group_ops: int
    group_ops: Dict[str, int]

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
            "baby_steps": self.baby_steps,
            "giant_steps": self.giant_steps,
            "total_steps": self.total_steps,
            "total_group_ops": self.total_group_ops,
            "group_ops": self.group_ops
        }

class DualDiffBSGSSolver:
    """
    Dual-End Projective Differential BSGS Solver.
    Uses 1D projective differential recurrence on BOTH baby steps and giant steps.
    Zero field inversions per step; batched with Montgomery's algorithm.
    Optimized asymmetric step allocation: m_b^* = floor(sqrt(N / 2)).
    """
    def __init__(self, batch_size: int = 32):
        self.batch_size = batch_size

    def solve(
        self,
        L: int,
        R: int,
        P_target: Tuple[int, int],
        baby_table: Optional[DualDiffBabyTable] = None
    ) -> DualDiffResult:
        N = R - L + 1
        t0 = time.perf_counter()
        ops = GroupOpCounters()

        # Optimal asymmetric allocation: m_b = floor(sqrt(N / 2))
        m_b = max(1, math.isqrt(N // 2))
        W = 2 * m_b + 1
        m_g = math.ceil(N / W) + 1

        # -------------------------------------------------------------
        # Phase 1: Baby-step table (or reuse)
        # -------------------------------------------------------------
        t_baby_start = time.perf_counter()
        if baby_table is None:
            baby_table = DualDiffBabyTable.build(m_b)
            ops.jacobian_adds += baby_table.op_counts.jacobian_adds
            ops.affine_conversions += baby_table.op_counts.affine_conversions
        t_baby = time.perf_counter() - t_baby_start

        # -------------------------------------------------------------
        # Phase 2: Instance-specific base offset
        # -------------------------------------------------------------
        t_inst_start = time.perf_counter()
        P_target_jac = (P_target[0], P_target[1], 1)
        L_point = scalar_mult(L)
        L_neg_jac = (L_point[0], (-L_point[1]) % P, 1)

        # Q_0 = P_target - L * G
        Q0_jac = jacobian_add(P_target_jac, L_neg_jac)
        ops.jacobian_adds += 1
        t_inst = time.perf_counter() - t_inst_start

        # -------------------------------------------------------------
        # Phase 3: Online Differential Giant Steps
        # -------------------------------------------------------------
        t_online_start = time.perf_counter()
        found_k = None
        giant_step_count = 0

        # Step 0 check: Q_0 is infinity => k = L
        if Q0_jac[2] == 0:
            found_k = L
        else:
            Q0_aff = to_affine(Q0_jac)
            ops.affine_conversions += 1
            if Q0_aff[0] in baby_table.table:
                j = baby_table.table[Q0_aff[0]]
                for sgn in ([1, -1] if j > 0 else [0]):
                    cand_k = L + sgn * j
                    if L <= cand_k <= R and scalar_mult(cand_k) == P_target:
                        found_k = cand_k
                        break

        # Step constant: S = -W * G
        S_aff_pos = scalar_mult(W)
        xs = S_aff_pos[0]

        # Compute Q_1 = Q_0 + (-W * G) to bootstrap the 2nd-order recurrence
        if found_k is None:
            S_neg_aff = (S_aff_pos[0], (-S_aff_pos[1]) % P)
            Q1_jac = jacobian_add_affine(Q0_jac, S_neg_aff)
            ops.jacobian_adds += 1
            if Q1_jac[2] == 0:
                found_k = L + W
            else:
                Q1_aff = to_affine(Q1_jac)
                ops.affine_conversions += 1
                if Q1_aff[0] in baby_table.table:
                    j = baby_table.table[Q1_aff[0]]
                    for sgn in ([1, -1] if j > 0 else [0]):
                        cand_k = L + 1 * W + sgn * j
                        if L <= cand_k <= R and scalar_mult(cand_k) == P_target:
                            found_k = cand_k
                            break

        if found_k is None and m_g >= 2:
            X_prev, Z_prev = Q0_aff[0], 1
            X_curr, Z_curr = Q1_aff[0], 1
            b_const_4 = (4 * B) % P

            curr_step = 2
            while curr_step <= m_g and found_k is None:
                block_size = min(self.batch_size, m_g - curr_step + 1)
                proj_X = []
                proj_Z = []
                indices = []

                for _ in range(block_size):
                    xs_Z = (xs * Z_curr) % P
                    T1 = (X_curr - xs_Z) % P
                    T1_sq = (T1 * T1) % P
                    Z_next = (T1_sq * Z_prev) % P

                    if Z_next == 0:
                        cand_k = L + curr_step * W
                        if L <= cand_k <= R and scalar_mult(cand_k) == P_target:
                            found_k = cand_k
                            giant_step_count += 1
                            break

                    Z_curr_sq = (Z_curr * Z_curr) % P
                    term1 = (2 * X_curr * xs * (X_curr + xs_Z)) % P
                    term2 = (b_const_4 * Z_curr_sq) % P
                    T2 = (term1 + term2) % P

                    X_next = (T2 * Z_prev - X_prev * T1_sq) % P

                    proj_X.append(X_next)
                    proj_Z.append(Z_next)
                    indices.append(curr_step)
                    giant_step_count += 1

                    X_prev, Z_prev = X_curr, Z_curr
                    X_curr, Z_curr = X_next, Z_next
                    curr_step += 1

                if found_k is not None:
                    break

                inv_Z = montgomery_batch_invert(proj_Z)
                ops.affine_conversions += 1

                for i_idx, step_i in enumerate(indices):
                    x_aff = (proj_X[i_idx] * inv_Z[i_idx]) % P
                    if x_aff in baby_table.table:
                        j = baby_table.table[x_aff]
                        for sgn in ([1, -1] if j > 0 else [0]):
                            cand_k = L + step_i * W + sgn * j
                            if L <= cand_k <= R and scalar_mult(cand_k) == P_target:
                                found_k = cand_k
                                break
                    if found_k is not None:
                        break

        t_online = time.perf_counter() - t_online_start
        t_total = time.perf_counter() - t0

        return DualDiffResult(
            success=(found_k is not None),
            recovered_key=found_k,
            L=L,
            R=R,
            N=N,
            m_b=m_b,
            W=W,
            t_baby=t_baby,
            t_instance=t_inst,
            t_online=t_online,
            t_cold=t_total,
            t_warm=t_inst + t_online,
            baby_steps=m_b,
            giant_steps=giant_step_count,
            total_steps=m_b + giant_step_count,
            total_group_ops=ops.total(),
            group_ops=ops.to_dict()
        )
