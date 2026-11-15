"""
Interleaved Projective Differential BSGS Solver for secp256k1 Bounded DLP
Discovery Cycle 5: Composing 1D Differential Recurrence with Interleaved Scheduling

Synthesizes:
1. Galbraith-Wang-Zhang (2017) interleaved scheduling with bidirectional cross-checking:
   Early collision detection reduces average steps from ~1.414 * sqrt(N) to ~0.943 * sqrt(N).
2. Pure 1D Brier-Joye projective differential recurrence (6M + 2S per step, zero Y arithmetic):
   Applied to BOTH baby steps and giant steps.
3. Montgomery simultaneous batch inversion across blocks of size B:
   Batches affine conversions at block boundaries.
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

@dataclass(frozen=True)
class InterleavedDiffResult:
    success: bool
    recovered_key: Optional[int]
    L: int
    R: int
    N: int
    t_baby: float
    t_giant: float
    t_total: float
    baby_steps: int
    giant_steps: int
    total_steps: int
    total_group_ops: int
    average_step_constant: float
    group_ops: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "recovered_key": self.recovered_key,
            "recovered_key_hex": hex(self.recovered_key) if self.recovered_key is not None else None,
            "L": self.L,
            "R": self.R,
            "N": self.N,
            "t_baby_seconds": round(self.t_baby, 6),
            "t_giant_seconds": round(self.t_giant, 6),
            "t_total_seconds": round(self.t_total, 6),
            "baby_steps": self.baby_steps,
            "giant_steps": self.giant_steps,
            "total_steps": self.total_steps,
            "total_group_ops": self.total_group_ops,
            "average_step_constant": round(self.average_step_constant, 4),
            "group_ops": self.group_ops
        }

class InterleavedDiffBSGSSolver:
    """
    Interleaved Projective Differential BSGS Solver.
    Uses 1D Brier-Joye differential recurrence on both baby and giant steps,
    expanding them in balanced interleaved blocks and cross-checking at block boundaries.
    """
    def __init__(self, block_size: int = 16):
        self.block_size = block_size

    def solve(
        self,
        L: int,
        R: int,
        P_target: Tuple[int, int]
    ) -> InterleavedDiffResult:
        N = R - L + 1
        t0 = time.perf_counter()
        ops = GroupOpCounters()
        sqrt_N = max(4, math.isqrt(N))

        m_b_max = max(2, int(0.75 * sqrt_N))
        W = 2 * m_b_max + 1
        m_g_max = math.ceil(N / W) + 2

        baby_table: Dict[int, int] = {}
        giant_table: Dict[int, int] = {}
        baby_step_count = 0
        giant_step_count = 0
        found_k = None

        t_baby_total = 0.0
        t_giant_total = 0.0
        b_const_4 = (4 * B) % P

        # -------------------------------------------------------------
        # 1. Giant Step Initialization: Q_0 and Q_1
        # -------------------------------------------------------------
        t_g_start = time.perf_counter()
        P_tgt_jac = (P_target[0], P_target[1], 1)
        L_aff = scalar_mult(L)
        L_neg_jac = (L_aff[0], (-L_aff[1]) % P, 1)
        Q0_jac = jacobian_add(P_tgt_jac, L_neg_jac)
        ops.jacobian_adds += 1

        if Q0_jac[2] == 0:
            found_k = L
            Q0_aff = None
        else:
            Q0_aff = to_affine(Q0_jac)
            ops.affine_conversions += 1
            giant_table[Q0_aff[0]] = 0

        # Step point S = -W * G (for giant steps)
        S_pos = scalar_mult(W)
        xs_giant = S_pos[0]
        S_neg_aff = (S_pos[0], (-S_pos[1]) % P)

        if found_k is None and Q0_aff is not None:
            Q1_jac = jacobian_add_affine(Q0_jac, S_neg_aff)
            ops.jacobian_adds += 1
            if Q1_jac[2] == 0:
                found_k = L + W
                Q1_aff = None
            else:
                Q1_aff = to_affine(Q1_jac)
                ops.affine_conversions += 1
                giant_table[Q1_aff[0]] = 1
                giant_step_count = 1
        else:
            Q1_aff = None
        t_giant_total += (time.perf_counter() - t_g_start)

        # -------------------------------------------------------------
        # 2. Baby Step Initialization: j=1 (G) and j=2 (2G)
        # -------------------------------------------------------------
        t_b_start = time.perf_counter()
        baby_table[GX] = 1
        baby_step_count = 1
        G2_aff = scalar_mult(2)
        baby_table[G2_aff[0]] = 2
        baby_step_count = 2
        ops.jacobian_adds += 1

        # Check initial matches between {Q0, Q1} and {G, 2G}
        if found_k is None:
            for q_aff, gi in [(Q0_aff, 0), (Q1_aff, 1)]:
                if q_aff is not None and q_aff[0] in baby_table:
                    j_match = baby_table[q_aff[0]]
                    for sgn in ([1, -1] if j_match > 0 else [0]):
                        cand = L + gi * W + sgn * j_match
                        if L <= cand <= R and scalar_mult(cand) == P_target:
                            found_k = cand
                            break
                if found_k is not None:
                    break
        t_baby_total += (time.perf_counter() - t_b_start)

        # State for giant differential recurrence
        if Q0_aff is not None and Q1_aff is not None:
            g_X_prev, g_Z_prev = Q0_aff[0], 1
            g_X_curr, g_Z_curr = Q1_aff[0], 1
        else:
            g_X_prev = g_Z_prev = g_X_curr = g_Z_curr = None

        # State for baby differential recurrence
        b_X_prev, b_Z_prev = GX, 1
        b_X_curr, b_Z_curr = G2_aff[0], 1
        xs_baby = GX

        # Interleaved expansion loop
        b_next_j = 3
        g_next_i = 2

        while found_k is None and (b_next_j <= m_b_max or (g_next_i <= m_g_max and g_X_curr is not None)):
            # -------------------------------------------------------------
            # Sub-phase A: Baby Step Block (Projective Differential)
            # -------------------------------------------------------------
            if b_next_j <= m_b_max:
                t_b_round = time.perf_counter()
                b_limit = min(m_b_max, b_next_j + self.block_size - 1)
                proj_b_X = []
                proj_b_Z = []
                b_indices = []

                for j in range(b_next_j, b_limit + 1):
                    xs_Z = (xs_baby * b_Z_curr) % P
                    T1 = (b_X_curr - xs_Z) % P
                    T1_sq = (T1 * T1) % P
                    Z_next = (T1_sq * b_Z_prev) % P

                    Z_curr_sq = (b_Z_curr * b_Z_curr) % P
                    term1 = (2 * b_X_curr * xs_baby * (b_X_curr + xs_Z)) % P
                    term2 = (b_const_4 * Z_curr_sq) % P
                    T2 = (term1 + term2) % P
                    X_next = (T2 * b_Z_prev - b_X_prev * T1_sq) % P

                    proj_b_X.append(X_next)
                    proj_b_Z.append(Z_next)
                    b_indices.append(j)
                    baby_step_count += 1
                    ops.jacobian_adds += 1

                    b_X_prev, b_Z_prev = b_X_curr, b_Z_curr
                    b_X_curr, b_Z_curr = X_next, Z_next

                inv_b_Z = montgomery_batch_invert(proj_b_Z)
                ops.affine_conversions += 1

                for idx, j_val in enumerate(b_indices):
                    x_aff = (proj_b_X[idx] * inv_b_Z[idx]) % P
                    baby_table[x_aff] = j_val

                    # Cross-check against existing giant steps
                    if x_aff in giant_table:
                        gi = giant_table[x_aff]
                        for sgn in ([1, -1] if j_val > 0 else [0]):
                            cand = L + gi * W + sgn * j_val
                            if L <= cand <= R and scalar_mult(cand) == P_target:
                                found_k = cand
                                break
                    if found_k is not None:
                        break

                b_next_j = b_limit + 1
                t_baby_total += (time.perf_counter() - t_b_round)

            if found_k is not None:
                break

            # -------------------------------------------------------------
            # Sub-phase B: Giant Step Block (Projective Differential)
            # -------------------------------------------------------------
            if g_next_i <= m_g_max and g_X_curr is not None:
                t_g_round = time.perf_counter()
                g_limit = min(m_g_max, g_next_i + self.block_size - 1)
                proj_g_X = []
                proj_g_Z = []
                g_indices = []

                for gi in range(g_next_i, g_limit + 1):
                    xs_Z = (xs_giant * g_Z_curr) % P
                    T1 = (g_X_curr - xs_Z) % P
                    T1_sq = (T1 * T1) % P
                    Z_next = (T1_sq * g_Z_prev) % P

                    if Z_next == 0:
                        cand = L + gi * W
                        if L <= cand <= R and scalar_mult(cand) == P_target:
                            found_k = cand
                            giant_step_count += 1
                            break

                    Z_curr_sq = (g_Z_curr * g_Z_curr) % P
                    term1 = (2 * g_X_curr * xs_giant * (g_X_curr + xs_Z)) % P
                    term2 = (b_const_4 * Z_curr_sq) % P
                    T2 = (term1 + term2) % P
                    X_next = (T2 * g_Z_prev - g_X_prev * T1_sq) % P

                    proj_g_X.append(X_next)
                    proj_g_Z.append(Z_next)
                    g_indices.append(gi)
                    giant_step_count += 1
                    ops.jacobian_adds += 1

                    g_X_prev, g_Z_prev = g_X_curr, g_Z_curr
                    g_X_curr, g_Z_curr = X_next, Z_next

                if found_k is not None:
                    break

                inv_g_Z = montgomery_batch_invert(proj_g_Z)
                ops.affine_conversions += 1

                for idx, gi_val in enumerate(g_indices):
                    x_aff = (proj_g_X[idx] * inv_g_Z[idx]) % P
                    giant_table[x_aff] = gi_val

                    # Cross-check against existing baby steps
                    if x_aff in baby_table:
                        j_val = baby_table[x_aff]
                        for sgn in ([1, -1] if j_val > 0 else [0]):
                            cand = L + gi_val * W + sgn * j_val
                            if L <= cand <= R and scalar_mult(cand) == P_target:
                                found_k = cand
                                break
                    if found_k is not None:
                        break

                g_next_i = g_limit + 1
                t_giant_total += (time.perf_counter() - t_g_round)

        t_total = time.perf_counter() - t0
        total_steps = baby_step_count + giant_step_count
        step_constant = total_steps / max(1.0, math.sqrt(N))

        return InterleavedDiffResult(
            success=(found_k is not None),
            recovered_key=found_k,
            L=L,
            R=R,
            N=N,
            t_baby=t_baby_total,
            t_giant=t_giant_total,
            t_total=t_total,
            baby_steps=baby_step_count,
            giant_steps=giant_step_count,
            total_steps=total_steps,
            total_group_ops=ops.total(),
            average_step_constant=step_constant,
            group_ops=ops.to_dict()
        )
