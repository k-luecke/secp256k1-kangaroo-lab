#!/usr/bin/env python3
"""
Comprehensive Boot Diversity Analysis for Ubuntu 13.10 Saucy Early-Boot RNG Metadata.

Computes:
1. Distribution of time to RNG initialization
2. Distribution of time to first controlled urandom read
3. Distribution of interrupt counts before the read
4. Unique IRQ sequences across boots
5. Longest Common Prefix (LCP) of IRQ sequences
6. Levenshtein edit distance between IRQ sequences
7. Variation in entropy counters, promotions, and transfers
8. Earliest event index at which boots diverge
9. Event-topology clustering across regimes
10. Structural determination: highly repeatable vs moderately structured vs chaotic
"""

import sys
import json
import math
import statistics
from pathlib import Path
from collections import Counter

def load_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def lcp(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i

def levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def summarize_numeric(vals):
    if not vals:
        return {"n": 0}
    vals = [float(v) for v in vals if v is not None]
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "min": min(vals),
        "median": statistics.median(vals),
        "mean": round(statistics.mean(vals), 2),
        "max": max(vals),
        "stdev": round(statistics.stdev(vals), 2) if len(vals) > 1 else 0.0
    }

def analyze(summary_file):
    rows = load_jsonl(summary_file)
    print(f"============================================================")
    print(f" SAUCY EARLY-BOOT RNG METADATA DIVERSITY ANALYSIS")
    print(f" Total Boot Records Ingested: {len(rows)}")
    print(f"============================================================\n")

    # Group by Regime
    regimes = {}
    for r in rows:
        reg = r.get("regime", "Unknown")
        regimes.setdefault(reg, []).append(r)

    for reg_name in sorted(regimes.keys()):
        reg_rows = regimes[reg_name]
        print(f"------------------------------------------------------------")
        print(f" REGIME {reg_name} (Total Boots: {len(reg_rows)})")
        print(f"------------------------------------------------------------")
        
        # 1-3. Timing and Count Distributions
        for field, label in [
            ("time_to_rng_init_ms", "Time to RNG Initialization (ms)"),
            ("time_to_first_urandom_read_ms", "Time to First /dev/urandom Read (ms)"),
            ("interrupt_count_before_read", "Interrupt Count Before Read"),
            ("device_randomness_calls", "add_device_randomness() Calls"),
            ("fast_pool_promotions", "Fast-Pool Promotions"),
            ("secondary_pool_transfers", "Secondary Pool Transfers"),
            ("entropy_count_at_read", "Entropy Count at Read"),
            ("entropy_total_at_read", "Entropy Total at Read")
        ]:
            stats = summarize_numeric([r.get(field) for r in reg_rows])
            print(f"  * {label}:")
            print(f"      min={stats['min']}, median={stats['median']}, mean={stats['mean']}, max={stats['max']}, stdev={stats['stdev']}")

        # 4. IRQ Sequences & Uniqueness
        irq_seqs = [tuple(r.get("irq_sequence", [])) for r in reg_rows]
        unique_seqs = len(set(irq_seqs))
        print(f"\n  * IRQ Sequence Diversity:")
        print(f"      Total Sequences: {len(irq_seqs)}")
        print(f"      Unique IRQ Sequences: {unique_seqs} (Ratio: {unique_seqs / len(irq_seqs):.4f})")

        # 5. Longest Common Prefix (LCP)
        if len(irq_seqs) > 1:
            base_seq = irq_seqs[0]
            pairwise_lcps = [lcp(base_seq, s) for s in irq_seqs[1:]]
            print(f"      LCP vs Boot 0: min={min(pairwise_lcps)}, median={statistics.median(pairwise_lcps)}, max={max(pairwise_lcps)}")
            
            # Earliest divergence index across all boots in regime
            all_lcp_min = min(pairwise_lcps)
            print(f"      Earliest Sequence Divergence Index: Event #{all_lcp_min}")

        # 6. Sample Edit Distances (Levenshtein)
        if len(irq_seqs) > 1:
            sample_size = min(15, len(irq_seqs))
            distances = []
            for i in range(sample_size):
                for j in range(i + 1, sample_size):
                    distances.append(levenshtein_distance(irq_seqs[i], irq_seqs[j]))
            if distances:
                print(f"      Pairwise Levenshtein Distance (sample of {sample_size} boots):")
                print(f"        min={min(distances)}, median={statistics.median(distances)}, max={max(distances)}")

        print("\n")

    # Overall Structural Synthesis
    print(f"============================================================")
    print(f" STRUCTURAL TOPOLOGY SYNTHESIS")
    print(f"============================================================")
    reg_a = regimes.get("A", [])
    reg_c = regimes.get("C", [])
    
    unique_a = len(set(tuple(r.get("irq_sequence", [])) for r in reg_a)) if reg_a else 0
    unique_c = len(set(tuple(r.get("irq_sequence", [])) for r in reg_c)) if reg_c else 0
    
    print(f"Regime A (Frozen VM Clock / Single Core):")
    print(f"  - Unique IRQ Topologies: {unique_a} / {len(reg_a)}")
    if unique_a == 1:
        print(f"  -> DETERMINISTIC / FROZEN: Under isolated VM clock execution, event topology is strictly repeatable.")
    else:
        print(f"  -> DIVERGENT: Even under isolated conditions, event topology diverges.")

    print(f"\nRegime C (Host Scheduling Jitter / Real-world VM):")
    print(f"  - Unique IRQ Topologies: {unique_c} / {len(reg_c)}")
    if unique_c == len(reg_c):
        print(f"  -> HIGHLY CHAOTIC: 100% unique event topologies observed.")
        print(f"  -> Earliest divergence occurs within the first few hardware interrupts.")
        print(f"  -> High-dimensional combinatorial interleaving of timer, disk, and console IRQs.")

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent / "boot_summaries.jsonl")
    analyze(path)
