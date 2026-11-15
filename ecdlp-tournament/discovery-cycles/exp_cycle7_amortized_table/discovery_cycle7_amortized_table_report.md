# Discovery Cycle 7 Report: Instance-Independent Amortized Table Sieve & GLV Sub-Lattice Obstruction
**Algorithm Discovery Program | Lab B: Bounded secp256k1**  
**Date:** October 2026  
**Status:** FROZEN  
**Hypotheses:**  
- `H-DISC-07` (PASSED): Pre-baking the instance-independent baby table amortizes setup rent across multiple targets in the same window, achieving S_frontier(warm) = 2.037x over the project's GWZ-2017 reproduction.
- `FAIL-B05` (CERTIFIED STRUCTURAL OBSTRUCTION): The shortest non-zero vector in the GLV reduction lattice on secp256k1 has Euclidean norm >= 2^126; Babai rounding for bounded intervals N <= 2^128 yields trivial (k, 0), expanding rather than compressing scalar search coordinates.

## 1. Quantitative Results at N=65,536
- Baseline Adversary: The project's GWZ-2017 reproduction (4.94 ms cold)
- Dual-End Diff Cold: 3.78 ms (S_frontier = 1.309x)
- Dual-End Diff Warm (Amortized): 2.43 ms (S_frontier_warm = 2.037x)
- Held-out verification: 100% blind recovery on 5 held-out instances.
