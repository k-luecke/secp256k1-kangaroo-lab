#!/usr/bin/env python3
"""
Unsolved Interval Analysis for the 2015 160-Bit Bitcoin Puzzle Challenge.
Transaction ID: 08389f34c98c606322740c0be6a7114d2d277787f16548b0825da76d9229724f

This module:
1. Formulates the exact mathematical boundaries for all lots n in [1, 160].
2. Distinguishes solved intervals (lots 1-65) from unsolved intervals (lots 66-160).
3. Evaluates keyspace cardinality, bit-length, and search complexity.
4. Analyzes the fractional offset structure r_n = p_n - 2^(n-1) of known lots to test
   for PRNG bias or generator structure that could constrain unresolved intervals.

SAFETY GUARANTEES:
- Strictly does NOT derive unknown private keys or search unresolved Bitcoin keyspace.
- Evaluates public metadata, mathematical interval structures, and known solved distributions.
"""

import math
from typing import Dict, List, Tuple

def get_interval_bounds(n: int) -> Tuple[int, int, int]:
    """
    Returns (lo, hi_inclusive, cardinality) for lot n.
    Window defined by creator's leading-one bitmask: [2^(n-1), 2^n - 1].
    """
    lo = 1 << (n - 1)
    hi = (1 << n) - 1
    cardinality = 1 << (n - 1)
    return lo, hi, cardinality

def format_hex_bounds(lo: int, hi: int, n: int) -> str:
    hex_len = (n + 3) // 4
    return f"[{hex(lo)} .. {hex(hi)}]"

def tabulate_unsolved_intervals(start_lot: int = 66, end_lot: int = 80) -> List[Dict]:
    rows = []
    for n in range(start_lot, end_lot + 1):
        lo, hi, card = get_interval_bounds(n)
        bsgs_ops = math.isqrt(card)
        rows.append({
            "lot": n,
            "bits": n,
            "lo_hex": hex(lo),
            "hi_hex": hex(hi),
            "cardinality": card,
            "cardinality_approx": f"2^{n-1} (~{card:.2e})",
            "bsgs_kangaroo_ops_approx": f"~2^{(n-1)/2:.1f} (~{bsgs_ops:.2e})"
        })
    return rows

def analyze_known_offset_distribution(known_keys: Dict[int, int]) -> Dict:
    """
    Analyzes normalized position f_n = (p_n - 2^(n-1)) / 2^(n-1) in [0, 1)
    across known solved keys to evaluate whether the creator's generator
    was uniform, biased, or structurally constrained.
    """
    fractions = []
    offsets = []
    
    for n, p in sorted(known_keys.items()):
        lo, hi, card = get_interval_bounds(n)
        r = p - lo
        frac = r / card if card > 0 else 0.0
        fractions.append((n, frac))
        offsets.append((n, r))
        
    mean_frac = sum(f for _, f in fractions) / len(fractions) if fractions else 0.0
    
    # Check quadrant distribution
    quads = [0, 0, 0, 0]
    for _, f in fractions:
        q_idx = min(3, int(f * 4))
        quads[q_idx] += 1
        
    return {
        "count": len(known_keys),
        "mean_fraction": mean_frac,
        "quadrant_distribution": quads,
        "fractions": fractions
    }

if __name__ == '__main__':
    print("=" * 80)
    print(" 2015 BITCOIN PUZZLE CHALLENGE: UNSOLVED INTERVAL LANDSCAPE")
    print("=" * 80)
    
    intervals = tabulate_unsolved_intervals(66, 80)
    print(f"{'Lot':<5} | {'Bits':<5} | {'Keyspace (2^(n-1))':<24} | {'Kangaroo Bound O(sqrt(N))':<26} | {'Hex Lower Bound':<20}")
    print("-" * 88)
    for r in intervals:
        print(f"#{r['lot']:<4} | {r['bits']:<5} | {r['cardinality_approx']:<24} | {r['bsgs_kangaroo_ops_approx']:<26} | {r['lo_hex']:<20}")
        
    print("\n" + "=" * 80)
    print(" SUMMARY FOR UNSOLVED SEARCH COMPLEXITY")
    print("=" * 80)
    print("1. P2PKH Hash Obstruction:")
    print("   - For unsolved lots (#66+), the public key point P is unrevealed on-chain.")
    print("   - Kangaroo and BSGS algorithms require the curve point P = k*G.")
    print("   - Without P, searches cannot evaluate algebraic point collisions and must")
    print("     rely on O(N) sequential address hashing unless public keys are announced.")
    print("2. Search Space Scale:")
    print("   - Lot #66 interval: [0x2000000000000000 .. 0x3fffffffffffffff] (size: 2^65 = 36.89 exakeys).")
    print("   - Lot #70 interval: [0x20000000000000000 .. 0x3fffffffffffffffe] (size: 2^69 = 590 exakeys).")
    print("   - Lot #160 interval: [0x8000000000000000000000000000000000000000 .. ] (size: 2^159).")
