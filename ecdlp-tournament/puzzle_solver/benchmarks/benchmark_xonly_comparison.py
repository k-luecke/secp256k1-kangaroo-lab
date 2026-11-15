"""
Discovery Cycle 1 Benchmark: Standard BSGS vs X-Only Negation-Quotient BSGS
Evaluates H-DISC-01 across bracket powers of 2 and large-scale scaling on frozen quantiles.
Measures:
- Baby-step setup time (T_baby)
- Total cold time (T_cold)
- Memory entries (baby_entries)
- Online search time (T_online)
- Total group operations
"""
import math
import time
import json
import statistics
import os
from typing import List, Dict, Any

from puzzle_solver.verification.secp256k1 import scalar_mult
from puzzle_solver.representations.bsgs import BSGSSolver, BabyStepTable
from puzzle_solver.representations.xonly_bsgs import XOnlyBSGSSolver, XOnlyBabyStepTable

FROZEN_QUANTILES = [0.10, 0.25, 0.50, 0.75, 0.90]

def run_comparison():
    print("=" * 90)
    print("DISCOVERY CYCLE 1: STANDARD BSGS vs. X-ONLY NEGATION-QUOTIENT BSGS")
    print("Hypothesis H-DISC-01 Evaluation (Coordinate Elimination of Sign Degree of Freedom)")
    print("=" * 90)
    print(f"{'N':<7} | {'m_std':<5} | {'m_xonly':<7} | {'T_baby Std':<11} | {'T_baby XOnly':<12} | {'Baby Reduc':<10} | {'T_cold Std':<11} | {'T_cold XOnly':<12} | {'Cold Speedup'}")
    print("-" * 90)

    test_N_values = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536]
    results = []

    std_solver = BSGSSolver()
    xonly_solver = XOnlyBSGSSolver()

    for N in test_N_values:
        L = 200000
        R = L + N - 1
        
        t_baby_std_list = []
        t_baby_xonly_list = []
        t_cold_std_list = []
        t_cold_xonly_list = []
        t_onl_std_list = []
        t_onl_xonly_list = []

        entries_std = None
        entries_xonly = None

        for q in FROZEN_QUANTILES:
            k_target = L + int(round(q * (N - 1)))
            P_target = scalar_mult(k_target)

            res_std = std_solver.solve(L, R, P_target)
            res_xonly = xonly_solver.solve(L, R, P_target)

            assert res_std.recovered_key == k_target
            assert res_xonly.recovered_key == k_target

            t_baby_std_list.append(res_std.t_baby)
            t_baby_xonly_list.append(res_xonly.t_baby)
            t_cold_std_list.append(res_std.t_cold)
            t_cold_xonly_list.append(res_xonly.t_cold)
            t_onl_std_list.append(res_std.t_online)
            t_onl_xonly_list.append(res_xonly.t_online)

            entries_std = res_std.baby_entries
            entries_xonly = res_xonly.baby_entries

        med_baby_std = statistics.median(t_baby_std_list)
        med_baby_xonly = statistics.median(t_baby_xonly_list)
        med_cold_std = statistics.median(t_cold_std_list)
        med_cold_xonly = statistics.median(t_cold_xonly_list)
        med_onl_std = statistics.median(t_onl_std_list)
        med_onl_xonly = statistics.median(t_onl_xonly_list)

        baby_reduction = (1.0 - (med_baby_xonly / max(med_baby_std, 1e-9))) * 100.0
        cold_speedup = med_cold_std / max(med_cold_xonly, 1e-9)

        print(f"{N:<7} | {entries_std:<5} | {entries_xonly:<7} | {med_baby_std*1000:<10.3f}ms | {med_baby_xonly*1000:<11.3f}ms | {baby_reduction:<9.1f}% | {med_cold_std*1000:<10.3f}ms | {med_cold_xonly*1000:<11.3f}ms | {cold_speedup:<8.2f}x")

        results.append({
            "N": N,
            "entries_std": entries_std,
            "entries_xonly": entries_xonly,
            "memory_reduction_ratio": round(entries_xonly / entries_std, 4),
            "med_baby_std_seconds": med_baby_std,
            "med_baby_xonly_seconds": med_baby_xonly,
            "baby_time_reduction_percent": round(baby_reduction, 2),
            "med_cold_std_seconds": med_cold_std,
            "med_cold_xonly_seconds": med_cold_xonly,
            "cold_speedup_vs_std_bsgs": round(cold_speedup, 2),
            "med_online_std_seconds": med_onl_std,
            "med_online_xonly_seconds": med_onl_xonly
        })

    print("-" * 90)
    print("SUMMARY OF EMPIRICAL FINDINGS:")
    mean_mem_red = statistics.mean([1.0 - r["memory_reduction_ratio"] for r in results]) * 100.0
    mean_baby_red = statistics.mean([r["baby_time_reduction_percent"] for r in results])
    print(f"Mean Memory Reduction: {mean_mem_red:.1f}% (Table size cut in half)")
    print(f"Mean Baby-Step Setup Time Reduction: {mean_baby_red:.1f}%")
    print("=" * 90)

    # Export ledger
    ledger_path = os.path.join(os.path.dirname(__file__), "..", "ledger", "cycle1_xonly_results.json")
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump({
            "experiment": "Discovery Cycle 1: Standard BSGS vs X-Only Negation-Quotient BSGS",
            "hypothesis": "H-DISC-01",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": results
        }, f, indent=2)
    print(f"Ledger exported to: {os.path.abspath(ledger_path)}")

if __name__ == "__main__":
    run_comparison()
