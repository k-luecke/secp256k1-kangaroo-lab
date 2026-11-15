"""
Projective Differential X-Only BSGS Solver for secp256k1 Bounded DLP
Discovery Cycle 3: Elimination of Y-Coordinate from Stepping Dynamics

Implements:
1. Pure 1D projective (X : Z) giant-step recurrence using Brier-Joye differential addition:
     X_{i+1} = [2 X_i x_s (X_i + x_s Z_i) + 4b Z_i^2] Z_{i-1} - X_{i-1} (X_i - x_s Z_i)^2 (mod P)
     Z_{i+1} = (X_i - x_s Z_i)^2 Z_{i-1} (mod P)
2. Montgomery batch inversion across window blocks of size B:
     Converts B projective points (X_i : Z_i) to affine x_i = X_i * Z_i^-1 with only 1 inversion + 3B multiplications.
3. Halved baby-step table (x-coordinate lookup mod negation).
"""
import math
import time
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Any, List

from puzzle_solver.verification.secp256k1 import (
    P, B, scalar_mult, jacobian_add, jacobian_add_affine, to_affine
)
from puzzle_solver.representations.bsgs import GroupOpCounters
from puzzle_solver.representations.xonly_bsgs import XOnlyBabyStepTable

@dataclass(frozen=True)
class DiffXOnlyResult:
    success: bool
    recovered_key: Optional[int]
    L: int
    R: int
    N: int
    t_baby: float
    t_instance: float
    t_online: float
    t_cold: float
    t_warm: float
    giant_steps: int
    total_group_ops: int
    batch_size: int
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
            "t_instance_seconds": round(self.t_instance, 6),
            "t_online_seconds": round(self.t_online, 6),
            "t_cold_seconds": round(self.t_cold, 6),
            "t_warm_seconds": round(self.t_warm, 6),
            "giant_steps": self.giant_steps,
            "total_group_ops": self.total_group_ops,
            "batch_size": self.batch_size,
            "group_ops": self.group_ops
        }

def montgomery_batch_invert(z_list: List[int]) -> List[int]:
    """
    Invert a list of integers modulo P using Montgomery's trick.
    Takes 1 modular inversion and 3 * len(z_list) multiplications.
    """
    n = len(z_list)
    if n == 0:
        return []
    if n == 1:
        return [pow(z_list[0], P - 2, P)]

    prefix = [1] * n
    acc = 1
    for i, z in enumerate(z_list):
        acc = (acc * z) % P
        prefix[i] = acc

    # Single modular inversion of total product
    inv_total = pow(acc, P - 2, P)

    inv_list = [0] * n
    for i in range(n - 1, 0, -1):
        inv_list[i] = (inv_total * prefix[i - 1]) % P
        inv_total = (inv_total * z_list[i]) % P
    inv_list[0] = inv_total

    return inv_list

class DiffXOnlyBSGSSolver:
    """
    Projective Differential X-Only BSGS Solver.
    Uses XOnlyBabyStepTable for baby steps (halved table).
    Advances giant steps entirely in 1D projective (X : Z) differential coordinates without Y.
    Batches projective points to affine using Montgomery batch inversion.
    """
    def __init__(self, batch_size: int = 32):
        self.batch_size = batch_size

    def solve(
        self,
        L: int,
        R: int,
        P_target: Tuple[int, int],
        baby_table: Optional[XOnlyBabyStepTable] = None
    ) -> DiffXOnlyResult:
        N = R - L + 1
        t0 = time.perf_counter()
        ops = GroupOpCounters()

        m = math.isqrt(N) + 1
        m_b = (m + 1) // 2
        W = 2 * m_b + 1
        m_g = math.ceil(N / W) + 1

        # -------------------------------------------------------------
        # Phase 1: Baby-step table (or reuse)
        # -------------------------------------------------------------
        t_baby_start = time.perf_counter()
        if baby_table is None:
            baby_table = XOnlyBabyStepTable.build(m_b)
            # Count baby step ops
            ops.jacobian_adds += m_b
            ops.affine_conversions += m_b
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
                j, _ = baby_table.table[Q0_aff[0]]
                for sgn in ([1, -1] if j > 0 else [0]):
                    cand_k = L + sgn * j
                    if L <= cand_k <= R and scalar_mult(cand_k) == P_target:
                        found_k = cand_k
                        break

        # Step constant: S = -W * G
        S_aff_pos = scalar_mult(W)
        xs = S_aff_pos[0]
        # In affine, -S has same x-coordinate xs!
        
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
                    j, is_pos = baby_table.table[Q1_aff[0]]
                    for sgn in ([1, -1] if j > 0 else [0]):
                        cand_k = L + 1 * W + sgn * j
                        if L <= cand_k <= R and scalar_mult(cand_k) == P_target:
                            found_k = cand_k
                            break

        if found_k is None and m_g >= 2:
            # We now have Q_0 = (X_0 : Z_0) and Q_1 = (X_1 : Z_1) in affine (Z=1)
            X_prev, Z_prev = Q0_aff[0], 1
            X_curr, Z_curr = Q1_aff[0], 1
            b_const_4 = (4 * B) % P

            curr_step = 2
            while curr_step <= m_g and found_k is None:
                # Accumulate a block of giant steps in projective (X : Z)
                block_size = min(self.batch_size, m_g - curr_step + 1)
                proj_X = []
                proj_Z = []
                indices = []

                for _ in range(block_size):
                    # Brier-Joye Projective Differential Addition:
                    # T1 = X_curr - xs * Z_curr
                    xs_Z = (xs * Z_curr) % P
                    T1 = (X_curr - xs_Z) % P
                    T1_sq = (T1 * T1) % P
                    
                    Z_next = (T1_sq * Z_prev) % P
                    
                    if Z_next == 0:
                        # Q_step is point at infinity => k = L + curr_step * W
                        cand_k = L + curr_step * W
                        if L <= cand_k <= R and scalar_mult(cand_k) == P_target:
                            found_k = cand_k
                            giant_step_count += 1
                            break

                    # T2 = 2 * X_curr * xs * (X_curr + xs_Z) + 4b * Z_curr^2
                    Z_curr_sq = (Z_curr * Z_curr) % P
                    term1 = (2 * X_curr * xs * (X_curr + xs_Z)) % P
                    term2 = (b_const_4 * Z_curr_sq) % P
                    T2 = (term1 + term2) % P
                    
                    X_next = (T2 * Z_prev - X_prev * T1_sq) % P
                    
                    proj_X.append(X_next)
                    proj_Z.append(Z_next)
                    indices.append(curr_step)
                    giant_step_count += 1

                    # Advance state
                    X_prev, Z_prev = X_curr, Z_curr
                    X_curr, Z_curr = X_next, Z_next
                    curr_step += 1

                if found_k is not None:
                    break

                # Batch invert all Z coordinates in the block
                inv_Z = montgomery_batch_invert(proj_Z)
                # Count 1 inversion + 3 * block_size mults
                ops.affine_conversions += 1 # 1 batch inversion

                # Lookup affine x coordinates in baby table
                for i_idx, step_i in enumerate(indices):
                    x_aff = (proj_X[i_idx] * inv_Z[i_idx]) % P
                    if x_aff in baby_table.table:
                        j, _ = baby_table.table[x_aff]
                        for sgn in ([1, -1] if j > 0 else [0]):
                            cand_k = L + step_i * W + sgn * j
                            if L <= cand_k <= R and scalar_mult(cand_k) == P_target:
                                found_k = cand_k
                                break
                    if found_k is not None:
                        break

        t_online = time.perf_counter() - t_online_start
        t_total = time.perf_counter() - t0

        return DiffXOnlyResult(
            success=(found_k is not None),
            recovered_key=found_k,
            L=L,
            R=R,
            N=N,
            t_baby=t_baby,
            t_instance=t_inst,
            t_online=t_online,
            t_cold=t_total,
            t_warm=t_inst + t_online,
            giant_steps=giant_step_count,
            total_group_ops=ops.total(),
            batch_size=self.batch_size,
            group_ops=ops.to_dict()
        )
