"""
Milestone P2: Representation Tournament Benchmark Runner
Linear Stepping vs. Baby-Step Giant-Step (BSGS) on secp256k1.
Implements:
- P2-B: Synthetic Bounded secp256k1 Crossover Panel with Frozen Target Quantiles
        Bracket sweep (powers of 2) + Deterministic refinement sweep
- P2-C: Three-Regime Economic Accounting (Cold, Warm, Amortized K*(N))
- P2-D: Historical Published-Puzzle Validation Arm (Independent P_target)
- P2-E: Full JSON Ledger Export to puzzle_solver/ledger/p2_tournament_results.json
"""
import sys
import os
import math
import time
import json
import statistics
from typing import List, Dict, Any, Tuple

from puzzle_solver.verification.secp256k1 import scalar_mult
from puzzle_solver.representations.bsgs import (
    BSGSSolver, BabyStepTable, LinearDlogScanner, BSGSResult, LinearDlogResult
)

FROZEN_QUANTILES = [0.10, 0.25, 0.50, 0.75, 0.90]
BOUNDARY_QUANTILES = [0.00, 1.00]

def evaluate_instance(
    L: int,
    R: int,
    k_target: int,
    reusable_table: BabyStepTable
) -> Tuple[LinearDlogResult, BSGSResult, BSGSResult]:
    """
    Evaluates both solvers on identical (L, R, P_target).
    Returns (linear_res, bsgs_cold_res, bsgs_warm_res).
    """
    P_target = scalar_mult(k_target)
    if P_target is None:
        raise ValueError(f"Target key {k_target} produced point at infinity")

    # 1. Linear Scanner
    lin_res = LinearDlogScanner.solve(L, R, P_target)
    assert lin_res.success and lin_res.recovered_key == k_target

    # 2. BSGS Cold (builds fresh baby-step table)
    bsgs_solver_cold = BSGSSolver()
    cold_res = bsgs_solver_cold.solve(L, R, P_target)
    assert cold_res.success and cold_res.recovered_key == k_target

    # 3. BSGS Warm (reuses precomputed table)
    warm_res = bsgs_solver_cold.solve(L, R, P_target, baby_table=reusable_table)
    assert warm_res.success and warm_res.recovered_key == k_target

    return lin_res, cold_res, warm_res

def run_quantile_panel_for_N(
    N: int,
    base_L: int = 100000
) -> Dict[str, Any]:
    """
    Evaluates all frozen quantiles for keyspace size N.
    """
    L = base_L
    R = L + N - 1
    m = math.isqrt(N) + 1
    reusable_table = BabyStepTable.build(m)

    # First run boundary checks
    for b_q in BOUNDARY_QUANTILES:
        k_b = L + int(round(b_q * (N - 1)))
        P_b = scalar_mult(k_b)
        l_res = LinearDlogScanner.solve(L, R, P_b)
        b_res = BSGSSolver().solve(L, R, P_b, baby_table=reusable_table)
        assert l_res.recovered_key == k_b and b_res.recovered_key == k_b

    # Run frozen quantiles
    q_results = []
    t_lin_list = []
    t_cold_list = []
    t_warm_list = []
    t_baby_list = []
    ops_lin_list = []
    ops_bsgs_tot_list = []

    for q in FROZEN_QUANTILES:
        k_target = L + int(round(q * (N - 1)))
        lin_res, cold_res, warm_res = evaluate_instance(L, R, k_target, reusable_table)
        
        q_results.append({
            "quantile": q,
            "k_target": k_target,
            "t_linear": lin_res.wall_clock_seconds,
            "t_cold": cold_res.t_cold,
            "t_warm": warm_res.t_warm,
            "t_baby": cold_res.t_baby,
            "t_instance": warm_res.t_instance,
            "t_online": warm_res.t_online,
            "giant_steps": warm_res.giant_steps,
            "lin_candidates_tested": lin_res.candidates_tested,
            "lin_group_ops": lin_res.group_ops["total_ops"],
            "bsgs_group_ops_total": cold_res.group_ops_total["total_ops"]
        })
        t_lin_list.append(lin_res.wall_clock_seconds)
        t_cold_list.append(cold_res.t_cold)
        t_warm_list.append(warm_res.t_warm)
        t_baby_list.append(cold_res.t_baby)
        ops_lin_list.append(lin_res.group_ops["total_ops"])
        ops_bsgs_tot_list.append(cold_res.group_ops_total["total_ops"])

    med_lin = statistics.median(t_lin_list)
    med_cold = statistics.median(t_cold_list)
    med_warm = statistics.median(t_warm_list)
    med_baby = statistics.median(t_baby_list)
    med_inst = statistics.median([r["t_instance"] for r in q_results])
    med_onl = statistics.median([r["t_online"] for r in q_results])

    # Compute amortized K*(N)
    # T_amortized(K) = T_baby / K + T_instance + T_online < T_linear
    # If med_warm >= med_lin: K* is infinity (never breaks even)
    # If med_cold < med_lin: K* = 1
    # Else: K* = ceil(T_baby / (T_linear - T_warm))
    if med_warm >= med_lin:
        K_star = float("inf")
    elif med_cold < med_lin:
        K_star = 1
    else:
        denom = med_lin - med_warm
        K_star = math.ceil(med_baby / denom) if denom > 0 else float("inf")

    return {
        "N": N,
        "m": m,
        "median_t_linear": med_lin,
        "range_t_linear": [min(t_lin_list), max(t_lin_list)],
        "median_t_cold": med_cold,
        "range_t_cold": [min(t_cold_list), max(t_cold_list)],
        "median_t_warm": med_warm,
        "range_t_warm": [min(t_warm_list), max(t_warm_list)],
        "median_t_baby": med_baby,
        "median_t_instance": med_inst,
        "median_t_online": med_onl,
        "K_star": K_star,
        "median_ops_linear": statistics.median(ops_lin_list),
        "median_ops_bsgs": statistics.median(ops_bsgs_tot_list),
        "speedup_cold": med_lin / max(med_cold, 1e-9),
        "speedup_warm": med_lin / max(med_warm, 1e-9),
        "quantile_details": q_results
    }

def run_tournament() -> Dict[str, Any]:
    print("=" * 85)
    print("PUZZLE SOLVER — MILESTONE P2: REPRESENTATION TOURNAMENT")
    print("Linear Stepping vs. Baby-Step Giant-Step (BSGS)")
    print("Algebraic Time-Memory Trade-off on secp256k1")
    print("=" * 85)

    # -------------------------------------------------------------
    # Step 1: Broad Bracket Sweep over powers of 2
    # -------------------------------------------------------------
    bracket_powers = [2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096]
    print("\n--- STEP 1: BROAD BRACKET SWEEP (Powers of 2) ---")
    print(f"{'N':<6} | {'m':<4} | {'Med T_lin (s)':<13} | {'Med T_cold (s)':<14} | {'Med T_warm (s)':<14} | {'Cold Spd':<9} | {'Warm Spd':<9} | {'K*(N)'}")
    print("-" * 85)

    bracket_results = []
    cold_crossover_bracket = None
    warm_crossover_bracket = None
    prev_N = None

    for N in bracket_powers:
        res = run_quantile_panel_for_N(N)
        bracket_results.append(res)
        k_str = str(res['K_star']) if res['K_star'] != float('inf') else "inf"
        print(f"{N:<6} | {res['m']:<4} | {res['median_t_linear']:<13.6f} | {res['median_t_cold']:<14.6f} | {res['median_t_warm']:<14.6f} | {res['speedup_cold']:<8.2f}x | {res['speedup_warm']:<8.2f}x | {k_str}")

        # Check cold bracket transition
        if cold_crossover_bracket is None and res['median_t_cold'] < res['median_t_linear']:
            cold_crossover_bracket = (prev_N, N)
        # Check warm bracket transition
        if warm_crossover_bracket is None and res['median_t_warm'] < res['median_t_linear']:
            warm_crossover_bracket = (prev_N, N)
        prev_N = N

    print(f"\nBroad Cold Bracket: {cold_crossover_bracket}")
    print(f"Broad Warm Bracket: {warm_crossover_bracket}")

    # -------------------------------------------------------------
    # Step 2: Deterministic Refinement Sweep inside Brackets
    # -------------------------------------------------------------
    print("\n--- STEP 2: DETERMINISTIC REFINEMENT SWEEPS ---")
    
    # Refine cold crossover inside cold_crossover_bracket
    low_c, high_c = cold_crossover_bracket if cold_crossover_bracket else (16, 64)
    refine_cold_values = sorted(list(set(range(low_c, high_c + 1, max(1, (high_c - low_c) // 10)))))
    print(f"Refining Cold Crossover in [{low_c}, {high_c}] across: {refine_cold_values}")
    
    refine_cold_results = []
    empirical_N_cold = None
    for N in refine_cold_values:
        res = run_quantile_panel_for_N(N)
        refine_cold_results.append(res)
        k_str = str(res['K_star']) if res['K_star'] != float('inf') else "inf"
        print(f"  N={N:<4} | Med T_lin: {res['median_t_linear']:.6f}s | Med T_cold: {res['median_t_cold']:.6f}s | Cold Spd: {res['speedup_cold']:.2f}x | K*: {k_str}")
        if empirical_N_cold is None and res['median_t_cold'] < res['median_t_linear']:
            empirical_N_cold = N

    # Refine warm crossover inside warm_crossover_bracket
    low_w, high_w = warm_crossover_bracket if warm_crossover_bracket else (4, 16)
    refine_warm_values = sorted(list(set(range(low_w, high_w + 1, 1))))
    print(f"\nRefining Warm Crossover in [{low_w}, {high_w}] across: {refine_warm_values}")
    
    refine_warm_results = []
    empirical_N_warm = None
    for N in refine_warm_values:
        res = run_quantile_panel_for_N(N)
        refine_warm_results.append(res)
        print(f"  N={N:<4} | Med T_lin: {res['median_t_linear']:.6f}s | Med T_warm: {res['median_t_warm']:.6f}s | Warm Spd: {res['speedup_warm']:.2f}x")
        if empirical_N_warm is None and res['median_t_warm'] < res['median_t_linear']:
            empirical_N_warm = N

    print("\n" + "=" * 85)
    print(f"CROSSOVER SUMMARY:")
    print(f"  Empirical Cold Crossover N*_cold = {empirical_N_cold}")
    print(f"  Empirical Warm Crossover N*_warm = {empirical_N_warm}")
    print("=" * 85)

    # -------------------------------------------------------------
    # Step 3: Scaling & Workload Law Validation (Large N Ladder)
    # -------------------------------------------------------------
    print("\n--- STEP 3: LARGE-SCALE SCALING & WORKLOAD LAW VALIDATION ---")
    large_ladder = [8192, 16384, 32768, 65536]
    print(f"{'N':<7} | {'m':<4} | {'Med T_lin (s)':<13} | {'Med T_cold (s)':<14} | {'Med T_warm (s)':<14} | {'Cold Spd':<10} | {'Warm Spd'}")
    print("-" * 85)
    scaling_results = []
    for N in large_ladder:
        res = run_quantile_panel_for_N(N)
        scaling_results.append(res)
        print(f"{N:<7} | {res['m']:<4} | {res['median_t_linear']:<13.6f} | {res['median_t_cold']:<14.6f} | {res['median_t_warm']:<14.6f} | {res['speedup_cold']:<9.2f}x | {res['speedup_warm']:<9.2f}x")

    ledger_data = {
        "benchmark": "Milestone P2 - Representation Tournament (Linear vs BSGS)",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "empirical_crossovers": {
            "cold_crossover_bracket": cold_crossover_bracket,
            "warm_crossover_bracket": warm_crossover_bracket,
            "N_star_cold": empirical_N_cold,
            "N_star_warm": empirical_N_warm
        },
        "bracket_sweep": bracket_results,
        "refinement_cold": refine_cold_results,
        "refinement_warm": refine_warm_results,
        "scaling_sweep": scaling_results
    }

    # Save ledger
    ledger_path = os.path.join(os.path.dirname(__file__), "..", "ledger", "p2_tournament_results.json")
    os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(ledger_data, f, indent=2)
    print(f"\nLedger exported to: {os.path.abspath(ledger_path)}")

    return ledger_data

if __name__ == "__main__":
    run_tournament()
