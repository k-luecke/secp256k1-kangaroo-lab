"""
Discovery Cycle 3 Benchmark: Projective Differential X-Only BSGS vs. Standard X-Only BSGS vs. Standard BSGS
Evaluates on the frozen quantile panel across N in [16, 65536].
Measures:
- Online giant-step time (T_online)
- Total cold and warm search times
- Operation counts and inversion amortization
- Speedup of Y-free projective differential recurrence
Exports results to puzzle_solver/ledger/cycle3_diff_xonly_results.json.
"""
import sys
import os
import math
import time
import json
import statistics
from typing import List, Dict, Any

from puzzle_solver.verification.secp256k1 import scalar_mult
from puzzle_solver.representations.bsgs import BSGSSolver, BabyStepTable
from puzzle_solver.representations.xonly_bsgs import XOnlyBSGSSolver, XOnlyBabyStepTable
from puzzle_solver.representations.diff_xonly_bsgs import DiffXOnlyBSGSSolver

FROZEN_QUANTILES = [0.10, 0.25, 0.50, 0.75, 0.90]
TEST_N_VALUES = [16, 64, 256, 1024, 4096, 16384, 65536]
BASE_L = 100000

def run_diff_benchmark() -> Dict[str, Any]:
    print("=" * 75)
    print("DISCOVERY CYCLE 3: PROJECTIVE DIFFERENTIAL X-ONLY BSGS BENCHMARK")
    print("=" * 75)

    solver_std = BSGSSolver()
    solver_xonly = XOnlyBSGSSolver()
    solver_diff = DiffXOnlyBSGSSolver(batch_size=32)

    results_by_N = {}

    for N in TEST_N_VALUES:
        L = BASE_L
        R = L + N - 1
        m_std = math.isqrt(N) + 1
        m_xonly = (m_std + 1) // 2

        # Precompute reusable baby-step tables
        std_table = BabyStepTable.build(m_std)
        xonly_table = XOnlyBabyStepTable.build(m_xonly)

        q_runs = []
        t_std_online = []
        t_xonly_online = []
        t_diff_online = []

        t_std_cold = []
        t_xonly_cold = []
        t_diff_cold = []

        t_std_warm = []
        t_xonly_warm = []
        t_diff_warm = []

        for q in FROZEN_QUANTILES:
            k_target = L + int(round(q * (N - 1)))
            P_target = scalar_mult(k_target)

            # 1. Standard BSGS
            s_res = solver_std.solve(L, R, P_target, baby_table=std_table)
            s_cold = solver_std.solve(L, R, P_target)
            assert s_res.success and s_res.recovered_key == k_target

            # 2. X-Only BSGS (Jacobian giant stepping)
            x_res = solver_xonly.solve(L, R, P_target, baby_table=xonly_table)
            x_cold = solver_xonly.solve(L, R, P_target)
            assert x_res.success and x_res.recovered_key == k_target

            # 3. Projective Differential X-Only BSGS
            d_res = solver_diff.solve(L, R, P_target, baby_table=xonly_table)
            d_cold = solver_diff.solve(L, R, P_target)
            assert d_res.success and d_res.recovered_key == k_target, f"Diff failed on N={N}, k={k_target}"

            q_runs.append({
                "quantile": q,
                "k_target": k_target,
                "t_online_std": s_res.t_online,
                "t_online_xonly": x_res.t_online,
                "t_online_diff": d_res.t_online,
                "t_cold_std": s_cold.t_cold,
                "t_cold_xonly": x_cold.t_cold,
                "t_cold_diff": d_cold.t_cold,
                "t_warm_std": s_res.t_warm,
                "t_warm_xonly": x_res.t_warm,
                "t_warm_diff": d_res.t_warm,
                "giant_steps_diff": d_res.giant_steps
            })

            t_std_online.append(s_res.t_online)
            t_xonly_online.append(x_res.t_online)
            t_diff_online.append(d_res.t_online)

            t_std_cold.append(s_cold.t_cold)
            t_xonly_cold.append(x_cold.t_cold)
            t_diff_cold.append(d_cold.t_cold)

            t_std_warm.append(s_res.t_warm)
            t_xonly_warm.append(x_res.t_warm)
            t_diff_warm.append(d_res.t_warm)

        med_std_onl = statistics.median(t_std_online)
        med_xo_onl = statistics.median(t_xonly_online)
        med_diff_onl = statistics.median(t_diff_online)

        med_std_cold = statistics.median(t_std_cold)
        med_xo_cold = statistics.median(t_xonly_cold)
        med_diff_cold = statistics.median(t_diff_cold)

        med_std_warm = statistics.median(t_std_warm)
        med_xo_warm = statistics.median(t_xonly_warm)
        med_diff_warm = statistics.median(t_diff_warm)

        speedup_online_vs_xo = med_xo_onl / max(med_diff_onl, 1e-9)
        speedup_online_vs_std = med_std_onl / max(med_diff_onl, 1e-9)
        speedup_cold_vs_std = med_std_cold / max(med_diff_cold, 1e-9)

        results_by_N[str(N)] = {
            "N": N,
            "median_t_online_std": round(med_std_onl, 6),
            "median_t_online_xonly": round(med_xo_onl, 6),
            "median_t_online_diff": round(med_diff_onl, 6),
            "median_t_cold_std": round(med_std_cold, 6),
            "median_t_cold_xonly": round(med_xo_cold, 6),
            "median_t_cold_diff": round(med_diff_cold, 6),
            "median_t_warm_std": round(med_std_warm, 6),
            "median_t_warm_xonly": round(med_xo_warm, 6),
            "median_t_warm_diff": round(med_diff_warm, 6),
            "speedup_online_vs_xonly": round(speedup_online_vs_xo, 3),
            "speedup_online_vs_std": round(speedup_online_vs_std, 3),
            "speedup_cold_vs_std": round(speedup_cold_vs_std, 3),
            "runs": q_runs
        }

        print(f"N={N:5d} | Online: Std={med_std_onl:7.5f}s, XO={med_xo_onl:7.5f}s, Diff={med_diff_onl:7.5f}s (Diff vs XO: {speedup_online_vs_xo:4.2f}x) | Cold: Diff={med_diff_cold:7.5f}s vs Std={med_std_cold:7.5f}s ({speedup_cold_vs_std:4.2f}x)")

    summary = {
        "metadata": {
            "title": "Discovery Cycle 3: Projective Differential X-Only BSGS Benchmark",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "quantiles": FROZEN_QUANTILES,
            "N_values": TEST_N_VALUES,
        },
        "results_by_N": results_by_N
    }

    ledger_path = os.path.join("puzzle_solver", "ledger", "cycle3_diff_xonly_results.json")
    with open(ledger_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nLedger exported to {ledger_path}")
    return summary

if __name__ == "__main__":
    run_diff_benchmark()
