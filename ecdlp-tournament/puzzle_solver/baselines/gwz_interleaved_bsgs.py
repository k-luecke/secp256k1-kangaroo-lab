"""
Galbraith-Wang-Zhang (GWZ-2017) Interleaved BSGS Baseline for Bounded secp256k1 DLP
Implements the state-of-the-art published interval-ECDLP algorithm from:
Galbraith, Wang, Zhang (2017), "Computing elliptic curve discrete logarithms with improved baby-step giant-step algorithm"

Features:
1. Interleaved baby-step and giant-step expansion:
   Instead of computing the entire baby table upfront, steps are interleaved in rounds/blocks.
   Achieves asymptotic average step count ~0.943 * sqrt(N) for random target keys.
2. Block computation via Montgomery simultaneous inversion:
   Amortizes field inversion cost across blocks of size B.
3. Negation automorphism quotient (x-only matching).
4. Serves as the state-of-the-art published adversary for Discovery Cycle 5.
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
class GWZResult:
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
    average_step_constant: float  # total_steps / sqrt(N)
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

class GWZInterleavedBSGSSolver:
    """
    Galbraith-Wang-Zhang Interleaved BSGS Solver.
    Interleaves baby-step and giant-step expansion in balanced blocks of size B.
    Uses negation map (x-only table) and Montgomery simultaneous inversion.
    """
    def __init__(self, block_size: int = 16):
        self.block_size = block_size

    def solve(
        self,
        L: int,
        R: int,
        P_target: Tuple[int, int]
    ) -> GWZResult:
        N = R - L + 1
        t0 = time.perf_counter()
        ops = GroupOpCounters()
        sqrt_N = max(4, math.isqrt(N))

        # Target step bounds:
        # In GWZ-2017 interleaved BSGS, optimal allocation yields:
        # Max baby steps m_b ~ 0.67 * sqrt_N, Max giant steps m_g ~ 0.67 * sqrt_N
        # Average total steps ~ 0.943 * sqrt_N
        m_b_max = max(2, int(0.75 * sqrt_N))
        W = 2 * m_b_max + 1
        m_g_max = math.ceil(N / W) + 2

        # Hash tables: x_coord -> index
        baby_table: Dict[int, int] = {}
        giant_table: Dict[int, int] = {}
        baby_step_count = 0
        giant_step_count = 0
        found_k = None

        t_baby_total = 0.0
        t_giant_total = 0.0

        # Step constant for giant steps: S = -W * G
        S_pos = scalar_mult(W)
        S_neg_aff = (S_pos[0], (-S_pos[1]) % P)

        # Giant step state initialization: Q_0 = P_target - L * G
        t_g_start = time.perf_counter()
        P_tgt_jac = (P_target[0], P_target[1], 1)
        L_aff = scalar_mult(L)
        L_neg_aff = (L_aff[0], (-L_aff[1]) % P)
        Q_jac = jacobian_add_affine(P_tgt_jac, L_neg_aff)
        ops.jacobian_adds += 1

        if Q_jac[2] == 0:
            found_k = L
        else:
            Q0_aff = to_affine(Q_jac)
            ops.affine_conversions += 1
            giant_table[Q0_aff[0]] = 0
        t_giant_total += (time.perf_counter() - t_g_start)

        # Baby step state initialization: starts at G (j=1)
        t_b_start = time.perf_counter()
        G_aff = (GX, GY)
        baby_jac = (GX, GY, 1)
        baby_table[GX] = 1
        baby_step_count = 1

        # Check if Q_0 matched G
        if found_k is None and Q0_aff is not None and Q0_aff[0] == GX:
            cand = L + 1
            if scalar_mult(cand) == P_target:
                found_k = cand
            else:
                cand = L - 1
                if scalar_mult(cand) == P_target:
                    found_k = cand
        t_baby_total += (time.perf_counter() - t_b_start)

        # Interleaved expansion loop
        b_block_idx = 2
        g_step_idx = 1
        curr_Q_jac = Q_jac

        while found_k is None and (b_block_idx <= m_b_max or g_step_idx <= m_g_max):
            # -------------------------------------------------------------
            # Sub-phase A: Baby Step Block Expansion (Montgomery Batched)
            # -------------------------------------------------------------
            if b_block_idx <= m_b_max:
                t_b_round = time.perf_counter()
                b_limit = min(m_b_max, b_block_idx + self.block_size - 1)
                jac_list = []
                j_indices = []

                for j in range(b_block_idx, b_limit + 1):
                    baby_jac = jacobian_add_affine(baby_jac, G_aff)
                    ops.jacobian_adds += 1
                    jac_list.append(baby_jac)
                    j_indices.append(j)
                    baby_step_count += 1

                # Montgomery batch conversion for baby block
                z_list = [pt[2] for pt in jac_list]
                inv_z = montgomery_batch_invert(z_list)
                ops.affine_conversions += 1

                for idx, pt in enumerate(jac_list):
                    z_inv = inv_z[idx]
                    z_inv2 = (z_inv * z_inv) % P
                    x_aff = (pt[0] * z_inv2) % P
                    j_val = j_indices[idx]
                    baby_table[x_aff] = j_val

                    # Cross-check new baby step against existing giant steps
                    if x_aff in giant_table:
                        gi = giant_table[x_aff]
                        for sgn in ([1, -1] if j_val > 0 else [0]):
                            cand = L + gi * W + sgn * j_val
                            if L <= cand <= R and scalar_mult(cand) == P_target:
                                found_k = cand
                                break
                    if found_k is not None:
                        break

                b_block_idx = b_limit + 1
                t_baby_total += (time.perf_counter() - t_b_round)

            if found_k is not None:
                break

            # -------------------------------------------------------------
            # Sub-phase B: Giant Step Block Expansion (Montgomery Batched)
            # -------------------------------------------------------------
            if g_step_idx <= m_g_max:
                t_g_round = time.perf_counter()
                g_limit = min(m_g_max, g_step_idx + self.block_size - 1)
                g_jac_list = []
                g_indices = []

                for gi in range(g_step_idx, g_limit + 1):
                    curr_Q_jac = jacobian_add_affine(curr_Q_jac, S_neg_aff)
                    ops.jacobian_adds += 1
                    g_jac_list.append(curr_Q_jac)
                    g_indices.append(gi)
                    giant_step_count += 1

                z_list = [pt[2] for pt in g_jac_list]
                inv_z = montgomery_batch_invert(z_list)
                ops.affine_conversions += 1

                for idx, pt in enumerate(g_jac_list):
                    if pt[2] == 0:
                        cand = L + g_indices[idx] * W
                        if L <= cand <= R and scalar_mult(cand) == P_target:
                            found_k = cand
                            break

                    z_inv = inv_z[idx]
                    z_inv2 = (z_inv * z_inv) % P
                    x_aff = (pt[0] * z_inv2) % P
                    gi_val = g_indices[idx]
                    giant_table[x_aff] = gi_val

                    # Cross-check new giant step against existing baby steps
                    if x_aff in baby_table:
                        j = baby_table[x_aff]
                        for sgn in ([1, -1] if j > 0 else [0]):
                            cand = L + gi_val * W + sgn * j
                            if L <= cand <= R and scalar_mult(cand) == P_target:
                                found_k = cand
                                break
                    if found_k is not None:
                        break

                g_step_idx = g_limit + 1
                t_giant_total += (time.perf_counter() - t_g_round)

        t_total = time.perf_counter() - t0
        total_steps = baby_step_count + giant_step_count
        step_constant = total_steps / max(1.0, math.sqrt(N))

        return GWZResult(
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
