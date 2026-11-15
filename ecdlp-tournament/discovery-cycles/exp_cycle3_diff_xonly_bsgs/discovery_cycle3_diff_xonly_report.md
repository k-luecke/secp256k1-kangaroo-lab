# Discovery Cycle 3 Report: Projective Differential X-Only Stepping + Montgomery Batch Inversion
**Algorithm Discovery Program | Lab B: Bounded secp256k1**  
**Date:** October 2026  
**Status:** FROZEN  
**Hypothesis:** `H-DISC-03` (PASSED, KNOWN_COMPOSITION)  
**Target Ledger:** `puzzle_solver/ledger/cycle3_diff_xonly_results.json`

---

## 1. Executive Summary

Discovery Cycle 3 applied the kernel coordinate-elimination operation directly to the **stepping dynamics** of discrete logarithm search. In prior cycles:
- Cycle 1 ($X$-Only BSGS) eliminated the $Y$-coordinate from stored baby steps using the negation automorphism $x(P) = x(-P)$, halving table size.
- Cycle 2 certified the Interval Boundary Obstruction, showing global group automorphisms beyond $\mathbb{Z}_2$ cannot quotient bounded intervals.

In Cycle 3, we observed that while $Y$ was quotiented out of the baby table, the online giant stepping operator continued to track full 3D Jacobian coordinates $(X, Y, Z)$ at $8M + 3S$ per step, followed by an expensive 256-bit Fermat Little Theorem field inversion ($pow(Z, P-2, P)$) at every step.

By deriving an exact 1D projective differential recurrence on secp256k1 ($y^2 = x^3 + 7$) using the Brier-Joye relation and coupling it with Montgomery batch inversion across blocks of size $B=32$:
1. **Coordinate Elimination:** The $Y$-coordinate was completely eliminated from the giant-stepping state. Stepping operates strictly on 1D projective $(X : Z)$ coordinates.
2. **Online Stepping Acceleration:** Online giant-step search time decreased by **$7.50\times$** at $N = 65,536$ ($0.00229$s vs $0.01718$s for Jacobian $X$-only BSGS).
3. **Cold Search Acceleration:** Total cold search time decreased by **$2.61\times$** at $N = 65,536$ ($0.02031$s vs $0.05300$s for Standard BSGS).
4. **Historical Validation:** 16/16 historical 2015 Bitcoin challenge puzzles were solved blindly under public $P_{\text{target}}$ quarantine in **0.0604s** (compared to 4.756s in P1 baseline and 0.178s in P2).
5. **Novelty Classification:** Audited under the novelty firewall as `KNOWN_COMPOSITION` (combining Brier-Joye Weierstrass differential addition, Bernstein-Montgomery batch inversion, and $X$-only negation quotient).

---

## 2. Mathematical Formulation & Derivation

### A. Weierstrass Differential Recurrence
For any points $P = (x_1, y_1)$ and $Q = (x_2, y_2)$ on $y^2 = x^3 + b$:
$$x(P+Q) + x(P-Q) = \frac{2 x_1 x_2 (x_1 + x_2) + 4b}{(x_1 - x_2)^2} \pmod P$$
Setting $Q_i$ as the current giant step and constant stride $S = -W G$, the previous step satisfies $Q_i - S = Q_{i-1}$.
In projective coordinates $(X : Z)$ where $x = X / Z$ and $S = (x_s : 1)$:
$$X_{i+1} = \left[ 2 X_i x_s (X_i + x_s Z_i) + 4b Z_i^2 \right] Z_{i-1} - X_{i-1} (X_i - x_s Z_i)^2 \pmod P$$
$$Z_{i+1} = (X_i - x_s Z_i)^2 Z_{i-1} \pmod P$$

### B. Operation Budget
- Tracking $Y$: Eliminated (0 field operations on $Y$).
- Inversions during recurrence: 0.
- Field multiplications per step: 6 multiplications, 2 squarings ($6M + 2S$).
- Montgomery batch inversion: Inverts $B = 32$ values of $Z$ simultaneously using 1 modular inversion + $3B$ field multiplications ($\approx 3$ multiplications per step equivalent).

---

## 3. Quantitative Tournament Results

Evaluated across the 5 frozen quantiles ($10\%, 25\%, 50\%, 75\%, 90\%$) for $N \in [16, 65536]$:

| $N$ | Online Std (s) | Online X-Only (s) | Online Diff (s) | **Online Speedup** | Cold Std (s) | Cold Diff (s) | **Cold Speedup** |
|---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 16 | 0.00042s | 0.00014s | 0.00069s | 0.20× | 0.00131s | 0.00120s | 1.10× |
| 64 | 0.00066s | 0.00041s | 0.00087s | 0.47× | 0.00215s | 0.00169s | 1.28× |
| 256 | 0.00120s | 0.00095s | 0.00091s | 1.05× | 0.00378s | 0.00226s | 1.67× |
| 1,024 | 0.00227s | 0.00204s | 0.00124s | 1.64× | 0.00702s | 0.00370s | 1.90× |
| 4,096 | 0.00487s | 0.00420s | 0.00130s | 3.23× | 0.01372s | 0.00598s | 2.30× |
| 16,384 | 0.00892s | 0.00856s | 0.00163s | 5.25× | 0.02666s | 0.01075s | 2.48× |
| 65,536 | 0.01765s | 0.01718s | 0.00229s | **7.50×** | 0.05300s | 0.02031s | **2.61×** |

---

## 4. Novelty & Governance Status
- Preregistered Hypothesis: `H-DISC-03`
- Status: `PASSED`
- Novelty Classification: `KNOWN_COMPOSITION`
- Gate Verification:
  - Gate A (Correctness): 100% agreement on all frozen quantiles and boundary cases.
  - Gate B (Operational Leverage): Giant-stepping reduced from $8M + 3S + 1I$ to $6M + 2S + 0.1I$.
  - Gate C (Total-Cost Accounting): $7.50\times$ online speedup, $2.61\times$ cold speedup.
