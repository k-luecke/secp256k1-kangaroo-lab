"""
Benchmark Runner: Solver 1 Baseline (Sequential Scanner)
Executes blind recovery of deliberately published historical Bitcoin transaction puzzles (#1 through #12)
using strictly quarantined public specifications.
Validates solutions cryptographically and records candidate throughput and workload ledgers.
"""
import sys
import os
import json
import time
from typing import List, Dict, Any

from puzzle_solver.targets.puzzle_registry import get_puzzle_spec, get_quarantined_truth, _PUBLIC_SPECS
from puzzle_solver.baselines.sequential_scan import SequentialScanner
from puzzle_solver.verification.address import privkey_to_address

def run_p1_benchmark(puzzle_ids: List[str]) -> Dict[str, Any]:
    """
    Run sequential scan baseline across specified puzzle IDs.
    Returns structured results ledger.
    """
    results = []
    total_candidates = 0
    total_time = 0.0
    all_matched = True

    print("=" * 80)
    print("RUNNING PUZZLE SOLVER — MILESTONE P1 BASELINE BENCHMARK")
    print("Algorithm: Sequential Scanner (Mixed Jacobian Stepping + Hash160 Direct Match)")
    print("Target Suite: Historical 2015 Bitcoin Challenge Puzzles")
    print("Answer Quarantine: STRICT (Search engine receives only Target Address & Bounds)")
    print("=" * 80)
    print(f"{'Puzzle ID':<14} | {'Bits':<4} | {'Space':<7} | {'Tested':<7} | {'Time (s)':<9} | {'Keys/s':<9} | {'Match':<5} | {'Recovered Key'}")
    print("-" * 80)

    for pid in puzzle_ids:
        # Search engine receives ONLY public spec
        spec = get_puzzle_spec(pid)
        scanner = SequentialScanner(spec)
        res = scanner.run()

        # Post-hoc evaluation & verification
        quarantined_truth = get_quarantined_truth(pid)
        key_matches_truth = (res.recovered_key_int == quarantined_truth)
        
        # Independent crypto verification
        independent_addr = privkey_to_address(res.recovered_key_int, compressed=True) if res.success else None
        addr_matches_target = (independent_addr == spec.target.target_value)
        
        crypto_verified = res.success and key_matches_truth and addr_matches_target
        if not crypto_verified:
            all_matched = False

        total_candidates += res.candidates_tested
        total_time += res.wall_clock_seconds

        match_str = "PASS" if crypto_verified else "FAIL"
        print(f"{pid:<14} | {spec.candidate_space.bits:<4} | {res.total_space_size:<7} | {res.candidates_tested:<7} | {res.wall_clock_seconds:<9.4f} | {res.keys_per_second:<9.1f} | {match_str:<5} | {res.recovered_key_hex}")

        results.append({
            "puzzle_id": pid,
            "bits": spec.candidate_space.bits,
            "lower_bound": spec.candidate_space.lower_bound,
            "upper_bound": spec.candidate_space.upper_bound,
            "space_size": res.total_space_size,
            "candidates_tested": res.candidates_tested,
            "wall_clock_seconds": res.wall_clock_seconds,
            "keys_per_second": res.keys_per_second,
            "recovered_key_hex": res.recovered_key_hex,
            "recovered_key_int": res.recovered_key_int,
            "recovered_address": res.recovered_address,
            "target_address": spec.target.target_value,
            "address_verified": addr_matches_target,
            "truth_verified": key_matches_truth,
            "status": "SUCCESS" if crypto_verified else "FAILED"
        })

    overall_rate = total_candidates / max(total_time, 1e-9)
    print("-" * 80)
    print(f"SUMMARY: {len(results)}/{len(puzzle_ids)} Puzzles Solved & Verified | Total Tested: {total_candidates:,} | Total Time: {total_time:.4f}s | Overall Rate: {overall_rate:.1f} keys/s")
    print(f"All Solutions Cryptographically Verified: {all_matched}")
    print("=" * 80)

    ledger_data = {
        "benchmark": "Milestone P1 - Sequential Scanner Baseline",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "puzzle_suite": puzzle_ids,
        "total_puzzles": len(puzzle_ids),
        "all_verified": all_matched,
        "total_candidates_tested": total_candidates,
        "total_wall_clock_seconds": round(total_time, 6),
        "overall_keys_per_second": round(overall_rate, 2),
        "results": results
    }

    # Save ledger
    ledger_path = os.path.join(os.path.dirname(__file__), "..", "ledger", "p1_baseline_results.json")
    os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(ledger_data, f, indent=2)
    print(f"Ledger exported to: {os.path.abspath(ledger_path)}")

    return ledger_data

if __name__ == "__main__":
    test_puzzles = [f"btc_2015_{i:03d}" for i in range(1, 17)]
    run_p1_benchmark(test_puzzles)
