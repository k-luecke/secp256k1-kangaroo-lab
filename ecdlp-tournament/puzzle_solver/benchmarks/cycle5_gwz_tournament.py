"""
Discovery Cycle 5 Tournament: Galbraith-Wang-Zhang (2017) State-of-the-Art Published Frontier
Compares:
1. Standard BSGS (Textbook 3D Jacobian)
2. Cycle 4 Dual-End Differential BSGS (Uniform Asymmetric 2-List)
3. GWZ-2017 Interleaved Block BSGS (Published State-of-the-Art Baseline)
4. Cycle 5 Interleaved Projective Differential BSGS (Differential Recurrence + Interleaved Scheduling)

Evaluates on the frozen quantile panel across N in [16, 65536].
Measures:
- Total wall-clock cold search time
- Average step count constant (steps / sqrt(N))
- Total group operations
- Speedup vs published GWZ-2017 baseline
Exports results to puzzle_solver/ledger/cycle5_gwz_tournament_results.json.
"""
import sys
import os
import math
import time
import json
import statistics
from typing import List, Dict, Any

from puzzle_solver.verification.secp256k1 import scalar_mult
from puzzle_solver.representations.bsgs import BSGSSolver
from puzzle_solver.representations.dual_diff_bsgs import DualDiffBSGSSolver
from puzzle_solver.baselines.gwz_interleaved_bsgs import GWZInterleavedBSGSSolver
from puzzle_solver.representations.interleaved_diff_bsgs import InterleavedDiffBSGSSolver

FROZEN_QUANTILES = [0.10, 0.25, 0.50, 0.75, 0.90]
TEST_N_VALUES = [16, 64, 256, 1024, 4096, 16384, 65536]
BASE_L = 100000

def run_cycle5_tournament() -> Dict[str, Any]:
    print("=" * 85)
    print("DISCOVERY CYCLE 5: GALBRAITH-WANG-ZHANG (2017) PUBLISHED FRONTIER TOURNAMENT")
    print("=" * 85)

    s_std = BSGSSolver()
    s_dual4 = DualDiffBSGSSolver(batch_size=32)
    s_gwz = GWZInterleavedBSGSSolver(block_size=16)
    s_intdiff = InterleavedDiffBSGSSolver(block_size=16)

    results_by_N = {}

    for N in TEST_N_VALUES:
        L = BASE_L
        R = L + N - 1

        q_runs = []
        t_std_l = []
        t_dual4_l = []
        t_gwz_l = []
        t_intdiff_l = []

        steps_gwz_l = []
        steps_intdiff_l = []
        steps_dual4_l = []

        ops_gwz_l = []
        ops_intdiff_l = []
        ops_dual4_l = []

        for q in FROZEN_QUANTILES:
            k_target = L + int(round(q * (N - 1)))
            P_target = scalar_mult(k_target)

            # 1. Standard BSGS Cold
            r_std = s_std.solve(L, R, P_target)
            assert r_std.success and r_std.recovered_key == k_target

            # 2. Dual-End Diff BSGS (Cycle 4)
            r_dual4 = s_dual4.solve(L, R, P_target)
            assert r_dual4.success and r_dual4.recovered_key == k_target

            # 3. GWZ-2017 Interleaved Baseline
            r_gwz = s_gwz.solve(L, R, P_target)
            assert r_gwz.success and r_gwz.recovered_key == k_target

            # 4. Cycle 5 Interleaved Diff BSGS
            r_intdiff = s_intdiff.solve(L, R, P_target)
            assert r_intdiff.success and r_intdiff.recovered_key == k_target, f"Failed on N={N}, k={k_target}"

            q_runs.append({
                "quantile": q,
                "k_target": k_target,
                "t_std": r_std.t_cold,
                "t_dual4": r_dual4.t_cold,
                "t_gwz": r_gwz.t_total,
                "t_intdiff": r_intdiff.t_total,
                "steps_dual4": r_dual4.total_steps,
                "steps_gwz": r_gwz.total_steps,
                "steps_intdiff": r_intdiff.total_steps,
                "c_gwz": r_gwz.average_step_constant,
                "c_intdiff": r_intdiff.average_step_constant,
                "ops_dual4": r_dual4.total_group_ops,
                "ops_gwz": r_gwz.total_group_ops,
                "ops_intdiff": r_intdiff.total_group_ops
            })

            t_std_l.append(r_std.t_cold)
            t_dual4_l.append(r_dual4.t_cold)
            t_gwz_l.append(r_gwz.t_total)
            t_intdiff_l.append(r_intdiff.t_total)

            steps_dual4_l.append(r_dual4.total_steps)
            steps_gwz_l.append(r_gwz.total_steps)
            steps_intdiff_l.append(r_intdiff.total_steps)

            ops_dual4_l.append(r_dual4.total_group_ops)
            ops_gwz_l.append(r_gwz.total_group_ops)
            ops_intdiff_l.append(r_intdiff.total_group_ops)

        med_std = statistics.median(t_std_l)
        med_dual4 = statistics.median(t_dual4_l)
        med_gwz = statistics.median(t_gwz_l)
        med_intdiff = statistics.median(t_intdiff_l)

        mean_c_gwz = statistics.mean([r["c_gwz"] for r in q_runs])
        mean_c_intdiff = statistics.mean([r["c_intdiff"] for r in q_runs])

        speedup_dual4_vs_gwz = med_gwz / max(med_dual4, 1e-9)
        speedup_intdiff_vs_gwz = med_gwz / max(med_intdiff, 1e-9)

        results_by_N[str(N)] = {
            "N": N,
            "median_t_std": round(med_std, 6),
            "median_t_dual4": round(med_dual4, 6),
            "median_t_gwz": round(med_gwz, 6),
            "median_t_intdiff": round(med_intdiff, 6),
            "mean_step_constant_gwz": round(mean_c_gwz, 4),
            "mean_step_constant_intdiff": round(mean_c_intdiff, 4),
            "speedup_dual4_vs_gwz": round(speedup_dual4_vs_gwz, 3),
            "speedup_intdiff_vs_gwz": round(speedup_intdiff_vs_gwz, 3),
            "median_steps_dual4": statistics.median(steps_dual4_l),
            "median_steps_gwz": statistics.median(steps_gwz_l),
            "median_steps_intdiff": statistics.median(steps_intdiff_l),
            "median_ops_dual4": statistics.median(ops_dual4_l),
            "median_ops_gwz": statistics.median(ops_gwz_l),
            "median_ops_intdiff": statistics.median(ops_intdiff_l),
            "runs": q_runs
        }

        print(f"N={N:5d} | Std: {med_std*1000:6.2f}ms | GWZ-2017: {med_gwz*1000:6.2f}ms (c={mean_c_gwz:.3f}) | Dual4: {med_dual4*1000:5.2f}ms ({speedup_dual4_vs_gwz:4.2f}x vs GWZ) | IntDiff: {med_intdiff*1000:5.2f}ms ({speedup_intdiff_vs_gwz:4.2f}x vs GWZ)")

    summary = {
        "metadata": {
            "title": "Discovery Cycle 5: Galbraith-Wang-Zhang (2017) Frontier Tournament",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "quantiles": FROZEN_QUANTILES,
            "N_values": TEST_N_VALUES,
        },
        "results_by_N": results_by_N
    }

    ledger_path = os.path.join("puzzle_solver", "ledger", "cycle5_gwz_tournament_results.json")
    with open(ledger_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nLedger exported to {ledger_path}")
    return summary

if __name__ == "__main__":
    run_cycle5_tournament()
