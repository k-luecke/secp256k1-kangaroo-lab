"""
Discovery Cycle 4 Benchmark: Dual-End Projective Differential BSGS vs. Cycle 3 vs. Cycle 1 vs. Standard BSGS vs. Kangaroo
Evaluates on the frozen quantile panel across N in [16, 65536].
Measures:
- Baby table setup time (T_baby)
- Online giant-step time (T_online)
- Total cold and warm search times
- Memory consumption (table entries)
- Full speedup ladder
Exports results to puzzle_solver/ledger/cycle4_dual_diff_results.json.
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
from puzzle_solver.representations.dual_diff_bsgs import DualDiffBSGSSolver, DualDiffBabyTable
from puzzle_solver.baselines.pollard_lambda import PollardLambdaScanner

FROZEN_QUANTILES = [0.10, 0.25, 0.50, 0.75, 0.90]
TEST_N_VALUES = [16, 64, 256, 1024, 4096, 16384, 65536]
BASE_L = 100000

def run_cycle4_benchmark() -> Dict[str, Any]:
    print("=" * 80)
    print("DISCOVERY CYCLE 4: DUAL-END PROJECTIVE DIFFERENTIAL BSGS BENCHMARK")
    print("=" * 80)

    solver_std = BSGSSolver()
    solver_xonly = XOnlyBSGSSolver()
    solver_diff3 = DiffXOnlyBSGSSolver(batch_size=32)
    solver_dual4 = DualDiffBSGSSolver(batch_size=32)
    solver_kang = PollardLambdaScanner()

    results_by_N = {}

    for N in TEST_N_VALUES:
        L = BASE_L
        R = L + N - 1

        # Parameter calculations
        m_std = math.isqrt(N) + 1
        m_xonly = (m_std + 1) // 2
        m_dual = max(1, math.isqrt(N // 2))

        # Build reusable tables for warm measurements
        std_tbl = BabyStepTable.build(m_std)
        xo_tbl = XOnlyBabyStepTable.build(m_xonly)
        dual_tbl = DualDiffBabyTable.build(m_dual)

        q_runs = []
        t_std_cold_l = []
        t_xo_cold_l = []
        t_diff3_cold_l = []
        t_dual4_cold_l = []
        t_kang_l = []

        t_std_onl_l = []
        t_xo_onl_l = []
        t_diff3_onl_l = []
        t_dual4_onl_l = []

        t_std_baby_l = []
        t_xo_baby_l = []
        t_dual4_baby_l = []

        for q in FROZEN_QUANTILES:
            k_target = L + int(round(q * (N - 1)))
            P_target = scalar_mult(k_target)

            # 1. Standard BSGS
            s_warm = solver_std.solve(L, R, P_target, baby_table=std_tbl)
            s_cold = solver_std.solve(L, R, P_target)
            assert s_cold.success and s_cold.recovered_key == k_target

            # 2. Cycle 1 X-Only BSGS
            x_warm = solver_xonly.solve(L, R, P_target, baby_table=xo_tbl)
            x_cold = solver_xonly.solve(L, R, P_target)
            assert x_cold.success and x_cold.recovered_key == k_target

            # 3. Cycle 3 Diff Giant BSGS
            d3_warm = solver_diff3.solve(L, R, P_target, baby_table=xo_tbl)
            d3_cold = solver_diff3.solve(L, R, P_target)
            assert d3_cold.success and d3_cold.recovered_key == k_target

            # 4. Cycle 4 Dual-End Diff BSGS
            d4_warm = solver_dual4.solve(L, R, P_target, baby_table=dual_tbl)
            d4_cold = solver_dual4.solve(L, R, P_target)
            assert d4_cold.success and d4_cold.recovered_key == k_target, f"Dual4 failed on N={N}, k={k_target}"

            # 5. Pollard Kangaroo
            k_res = solver_kang.solve(L, R, P_target)
            assert k_res.success and k_res.recovered_key == k_target

            q_runs.append({
                "quantile": q,
                "k_target": k_target,
                "t_std_cold": s_cold.t_cold,
                "t_xo_cold": x_cold.t_cold,
                "t_diff3_cold": d3_cold.t_cold,
                "t_dual4_cold": d4_cold.t_cold,
                "t_kang": k_res.t_total,
                "t_std_online": s_warm.t_online,
                "t_xo_online": x_warm.t_online,
                "t_diff3_online": d3_warm.t_online,
                "t_dual4_online": d4_warm.t_online,
                "t_std_baby": s_cold.t_baby,
                "t_xo_baby": x_cold.t_baby,
                "t_dual4_baby": d4_cold.t_baby,
                "mem_std": len(std_tbl.table),
                "mem_xo": len(xo_tbl.table),
                "mem_dual4": len(dual_tbl.table),
                "mem_kang_dps": k_res.distinguished_points_stored
            })

            t_std_cold_l.append(s_cold.t_cold)
            t_xo_cold_l.append(x_cold.t_cold)
            t_diff3_cold_l.append(d3_cold.t_cold)
            t_dual4_cold_l.append(d4_cold.t_cold)
            t_kang_l.append(k_res.t_total)

            t_std_onl_l.append(s_warm.t_online)
            t_xo_onl_l.append(x_warm.t_online)
            t_diff3_onl_l.append(d3_warm.t_online)
            t_dual4_onl_l.append(d4_warm.t_online)

            t_std_baby_l.append(s_cold.t_baby)
            t_xo_baby_l.append(x_cold.t_baby)
            t_dual4_baby_l.append(d4_cold.t_baby)

        med_std_cold = statistics.median(t_std_cold_l)
        med_xo_cold = statistics.median(t_xo_cold_l)
        med_diff3_cold = statistics.median(t_diff3_cold_l)
        med_dual4_cold = statistics.median(t_dual4_cold_l)
        med_kang = statistics.median(t_kang_l)

        med_std_onl = statistics.median(t_std_onl_l)
        med_xo_onl = statistics.median(t_xo_onl_l)
        med_diff3_onl = statistics.median(t_diff3_onl_l)
        med_dual4_onl = statistics.median(t_dual4_onl_l)

        med_std_baby = statistics.median(t_std_baby_l)
        med_xo_baby = statistics.median(t_xo_baby_l)
        med_dual4_baby = statistics.median(t_dual4_baby_l)

        speedup_cold_vs_std = med_std_cold / max(med_dual4_cold, 1e-9)
        speedup_cold_vs_diff3 = med_diff3_cold / max(med_dual4_cold, 1e-9)
        speedup_baby = med_std_baby / max(med_dual4_baby, 1e-9)
        speedup_kang = med_kang / max(med_dual4_cold, 1e-9)

        results_by_N[str(N)] = {
            "N": N,
            "median_t_cold_std": round(med_std_cold, 6),
            "median_t_cold_xonly": round(med_xo_cold, 6),
            "median_t_cold_diff3": round(med_diff3_cold, 6),
            "median_t_cold_dual4": round(med_dual4_cold, 6),
            "median_t_kangaroo": round(med_kang, 6),
            "median_t_online_dual4": round(med_dual4_onl, 6),
            "median_t_baby_std": round(med_std_baby, 6),
            "median_t_baby_dual4": round(med_dual4_baby, 6),
            "speedup_cold_vs_std": round(speedup_cold_vs_std, 3),
            "speedup_cold_vs_diff3": round(speedup_cold_vs_diff3, 3),
            "speedup_baby_table": round(speedup_baby, 3),
            "speedup_vs_kangaroo": round(speedup_kang, 3),
            "mem_std_entries": len(std_tbl.table),
            "mem_dual4_entries": len(dual_tbl.table),
            "runs": q_runs
        }

        print(f"N={N:5d} | Baby: Std={med_std_baby*1000:6.2f}ms, Dual4={med_dual4_baby*1000:5.2f}ms ({speedup_baby:5.1f}x) | Cold: Std={med_std_cold*1000:6.2f}ms, Dual4={med_dual4_cold*1000:5.2f}ms (Speedup: {speedup_cold_vs_std:5.2f}x vs Std, {speedup_kang:5.1f}x vs Kang)")

    summary = {
        "metadata": {
            "title": "Discovery Cycle 4: Dual-End Projective Differential BSGS Benchmark",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "quantiles": FROZEN_QUANTILES,
            "N_values": TEST_N_VALUES,
        },
        "results_by_N": results_by_N
    }

    ledger_path = os.path.join("puzzle_solver", "ledger", "cycle4_dual_diff_results.json")
    with open(ledger_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nLedger exported to {ledger_path}")
    return summary

if __name__ == "__main__":
    run_cycle4_benchmark()
