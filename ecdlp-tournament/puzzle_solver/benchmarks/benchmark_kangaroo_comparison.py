"""
Benchmark Comparison: Pollard's Kangaroo (Lambda) vs. BSGS vs. X-Only BSGS vs. Linear Stepping
Evaluates on the frozen quantile panel across N in [16, 65536].
Measures:
- Total wall time, setup/tame time, online/wild time
- Group operations (Jacobian additions, doublings, affine conversions)
- Memory consumption (table size / distinguished points stored)
- Time-Memory Pareto Frontier analysis
Exports results to puzzle_solver/ledger/control_kangaroo_results.json.
"""
import sys
import os
import math
import time
import json
import statistics
from typing import List, Dict, Any

from puzzle_solver.verification.secp256k1 import scalar_mult
from puzzle_solver.representations.bsgs import BSGSSolver, BabyStepTable, LinearDlogScanner
from puzzle_solver.representations.xonly_bsgs import XOnlyBSGSSolver, XOnlyBabyStepTable
from puzzle_solver.baselines.pollard_lambda import PollardLambdaScanner

FROZEN_QUANTILES = [0.10, 0.25, 0.50, 0.75, 0.90]
TEST_N_VALUES = [16, 64, 256, 1024, 4096, 16384, 65536]
BASE_L = 100000

def run_kangaroo_benchmark() -> Dict[str, Any]:
    print("=" * 70)
    print("CONTROL BRANCH BENCHMARK: POLLARD KANGAROO vs BSGS vs LINEAR")
    print("=" * 70)

    kangaroo = PollardLambdaScanner()
    bsgs_standard = BSGSSolver()
    bsgs_xonly = XOnlyBSGSSolver()

    results_by_N = {}

    for N in TEST_N_VALUES:
        L = BASE_L
        R = L + N - 1
        m_std = math.isqrt(N) + 1
        m_xonly = (m_std + 1) // 2

        # Precompute tables for warm BSGS
        std_table = BabyStepTable.build(m_std)
        xonly_table = XOnlyBabyStepTable.build(m_xonly)

        q_runs = []
        t_lin_list = []
        t_bsgs_cold_list = []
        t_bsgs_warm_list = []
        t_xonly_cold_list = []
        t_xonly_warm_list = []
        t_kang_list = []
        t_kang_tame_list = []
        t_kang_wild_list = []

        ops_lin_list = []
        ops_bsgs_cold_list = []
        ops_xonly_cold_list = []
        ops_kang_list = []

        mem_std_list = []
        mem_xonly_list = []
        mem_kang_list = []

        for q in FROZEN_QUANTILES:
            k_target = L + int(round(q * (N - 1)))
            P_target = scalar_mult(k_target)

            # 1. Linear Scanner
            lin_res = LinearDlogScanner.solve(L, R, P_target)
            assert lin_res.success and lin_res.recovered_key == k_target

            # 2. BSGS Standard Cold & Warm
            b_cold = bsgs_standard.solve(L, R, P_target)
            b_warm = bsgs_standard.solve(L, R, P_target, baby_table=std_table)
            assert b_cold.success and b_cold.recovered_key == k_target

            # 3. X-Only BSGS Cold & Warm
            x_cold = bsgs_xonly.solve(L, R, P_target)
            x_warm = bsgs_xonly.solve(L, R, P_target, baby_table=xonly_table)
            assert x_cold.success and x_cold.recovered_key == k_target

            # 4. Pollard Kangaroo
            k_res = kangaroo.solve(L, R, P_target)
            assert k_res.success and k_res.recovered_key == k_target, f"Kangaroo failed on N={N}, k={k_target}"

            q_runs.append({
                "quantile": q,
                "k_target": k_target,
                "t_linear": lin_res.wall_clock_seconds,
                "t_bsgs_cold": b_cold.t_cold,
                "t_bsgs_warm": b_warm.t_warm,
                "t_xonly_cold": x_cold.t_cold,
                "t_xonly_warm": x_warm.t_warm,
                "t_kangaroo": k_res.t_total,
                "t_kangaroo_tame": k_res.t_tame,
                "t_kangaroo_wild": k_res.t_wild,
                "ops_linear": lin_res.group_ops["total_ops"],
                "ops_bsgs_cold": b_cold.group_ops_total["total_ops"],
                "ops_xonly_cold": x_cold.group_ops_total["total_ops"],
                "ops_kangaroo": k_res.total_group_ops,
                "mem_bsgs_entries": len(std_table.table),
                "mem_xonly_entries": len(xonly_table.table),
                "mem_kangaroo_dps": k_res.distinguished_points_stored,
            })

            t_lin_list.append(lin_res.wall_clock_seconds)
            t_bsgs_cold_list.append(b_cold.t_cold)
            t_bsgs_warm_list.append(b_warm.t_warm)
            t_xonly_cold_list.append(x_cold.t_cold)
            t_xonly_warm_list.append(x_warm.t_warm)
            t_kang_list.append(k_res.t_total)
            t_kang_tame_list.append(k_res.t_tame)
            t_kang_wild_list.append(k_res.t_wild)

            ops_lin_list.append(lin_res.group_ops["total_ops"])
            ops_bsgs_cold_list.append(b_cold.group_ops_total["total_ops"])
            ops_xonly_cold_list.append(x_cold.group_ops_total["total_ops"])
            ops_kang_list.append(k_res.total_group_ops)

            mem_std_list.append(len(std_table.table))
            mem_xonly_list.append(len(xonly_table.table))
            mem_kang_list.append(k_res.distinguished_points_stored)

        med_lin = statistics.median(t_lin_list)
        med_bsgs_cold = statistics.median(t_bsgs_cold_list)
        med_bsgs_warm = statistics.median(t_bsgs_warm_list)
        med_xonly_cold = statistics.median(t_xonly_cold_list)
        med_xonly_warm = statistics.median(t_xonly_warm_list)
        med_kang = statistics.median(t_kang_list)
        med_kang_tame = statistics.median(t_kang_tame_list)
        med_kang_wild = statistics.median(t_kang_wild_list)

        med_ops_lin = statistics.median(ops_lin_list)
        med_ops_bsgs = statistics.median(ops_bsgs_cold_list)
        med_ops_xonly = statistics.median(ops_xonly_cold_list)
        med_ops_kang = statistics.median(ops_kang_list)

        med_mem_std = statistics.median(mem_std_list)
        med_mem_xonly = statistics.median(mem_xonly_list)
        med_mem_kang = statistics.median(mem_kang_list)

        results_by_N[str(N)] = {
            "N": N,
            "median_t_linear": round(med_lin, 6),
            "median_t_bsgs_cold": round(med_bsgs_cold, 6),
            "median_t_bsgs_warm": round(med_bsgs_warm, 6),
            "median_t_xonly_cold": round(med_xonly_cold, 6),
            "median_t_xonly_warm": round(med_xonly_warm, 6),
            "median_t_kangaroo": round(med_kang, 6),
            "median_t_kangaroo_tame": round(med_kang_tame, 6),
            "median_t_kangaroo_wild": round(med_kang_wild, 6),
            "speedup_kang_vs_linear": round(med_lin / max(med_kang, 1e-9), 3),
            "speedup_xonly_vs_kang": round(med_kang / max(med_xonly_cold, 1e-9), 3),
            "median_ops_linear": med_ops_lin,
            "median_ops_bsgs_cold": med_ops_bsgs,
            "median_ops_xonly_cold": med_ops_xonly,
            "median_ops_kangaroo": med_ops_kang,
            "median_mem_entries_bsgs": med_mem_std,
            "median_mem_entries_xonly": med_mem_xonly,
            "median_mem_entries_kangaroo": med_mem_kang,
            "runs": q_runs
        }

        print(f"N={N:5d} | Lin: {med_lin:8.5f}s | Kang: {med_kang:8.5f}s (DPs: {int(med_mem_kang):2d}) | BSGS-Cold: {med_bsgs_cold:8.5f}s | XOnly-Cold: {med_xonly_cold:8.5f}s")

    summary = {
        "metadata": {
            "title": "Pollard Kangaroo vs BSGS Tournament Benchmark",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "quantiles": FROZEN_QUANTILES,
            "N_values": TEST_N_VALUES,
        },
        "results_by_N": results_by_N
    }

    ledger_path = os.path.join("puzzle_solver", "ledger", "control_kangaroo_results.json")
    with open(ledger_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nLedger exported to {ledger_path}")
    return summary

if __name__ == "__main__":
    run_kangaroo_benchmark()
