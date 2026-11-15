# Discovery Cycle 4 Report: Dual-End Projective Differential BSGS & Tested Modular-Coordinate Obstruction
**Algorithm Discovery Program | Lab B: Bounded secp256k1**  
**Date:** October 2026  
**Status:** FROZEN  
**Hypotheses:**  
- `H-DISC-04` (PASSED, KNOWN_COMPOSITION): Dual-End Projective Differential BSGS with Uniform Asymmetric Ratio.  
- `FAIL-B03-TESTED-MODULAR-OBSTRUCTION` (EMPIRICALLY TESTED OBSTRUCTION): Direct affine coordinate parity predicates fail to correlate with scalar parity; representation family remains open.  
**Target Ledger:** `puzzle_solver/ledger/cycle4_dual_diff_results.json`

---

## 1. Executive Summary

Discovery Cycle 4 expanded the coordinate-elimination program along two fronts:
1. **Bilateral Coordinate Elimination (Dual-End Differential BSGS):** In Cycle 3, online giant stepping was accelerated by $7.50\times$, shifting the dominant computational bottleneck to baby-step table construction ($89\%$ of cold runtime). In Cycle 4, the 1D Brier-Joye projective differential recurrence and Montgomery batch inversion were extended to the baby-step phase, eliminating all $Y$-coordinate arithmetic and dictionary storage ($x \mapsto j$ instead of $x \mapsto (j, y)$) while tuning the asymmetric stride to the two-list uniform minimum $m_b^* = \lfloor \sqrt{N/2} \rfloor$.
2. **Tested Modular-Coordinate Obstruction:** Investigated whether bounded intervals can be quotiented into modular residue classes $k \equiv r \pmod M$. Empirical testing on direct affine parity predicates $x \pmod 2$ and $y \pmod 2$ showed no useful correlation with scalar parity. While prime order $n$ prevents direct proper subgroup projection, this result records the empirical failure of obvious direct coordinates rather than a blanket impossibility theorem; the representation family remains open for alternative surviving relations.

Key results:
- **Baby Table Setup Speedup:** Increased by **$24.3\times$** at $N = 65,536$ ($1.42$ ms vs $34.56$ ms for Standard BSGS).
- **Cold Search Total Speedup:** Increased by **$15.58\times$** at $N = 65,536$ ($3.35$ ms vs $52.13$ ms for Standard BSGS).
- **Speedup vs Pollard Kangaroo:** **$55.3\times$ faster** at $N = 65,536$ ($3.35$ ms vs $202.8$ ms).
- **Speedup vs Linear Stepping:** **$1,393\times$ faster** at $N = 65,536$ ($3.35$ ms vs $4,666.8$ ms). (Preserved as a historical baseline calibration; subsequent cycles escalate the adversary to the published Galbraith-Wang-Zhang 2017 frontier).
- **Historical Challenge Validation:** Solved 16/16 historical 2015 Bitcoin challenge puzzles blindly under public $P_{\text{target}}$ quarantine in **0.0247s** ($1.54$ ms/puzzle), achieving a cumulative $192.5\times$ speedup over the P1 linear baseline.

---

## 2. Mathematical Formulation & Optimizations

### A. Dual-End 1D Differential Recurrence
For both baby steps ($j \cdot G$) and giant steps ($Q_i = Q_0 - i W G$), points are generated via the 2nd-order projective recurrence:
$$X_{k+1} = \left[ 2 X_k x_s (X_k + x_s Z_k) + 4b Z_k^2 \right] Z_{k-1} - X_{k-1} (X_k - x_s Z_k)^2 \pmod P$$
$$Z_{k+1} = (X_k - x_s Z_k)^2 Z_{k-1} \pmod P$$
- Step stride for baby steps: $S = 1 \cdot G$ ($x_s = G_x$).
- Step stride for giant steps: $S = -W \cdot G$ ($x_s = x(W \cdot G)$).
- Per-step modular inversions: **Strictly 0**.
- Per-step arithmetic: 6 multiplications, 2 squarings ($6M + 2S$).
- Global conversion: All projective $Z$ coordinates are inverted simultaneously via Montgomery batch inversion (1 modular exponentiation $+ 3K$ multiplications).

### B. Uniform Asymmetric Step Allocation
Total steps in uniform two-list symmetric search: $C(m_b) = m_b + \frac{N}{2 m_b}$.
Minimizing $C(m_b)$ for this particular two-list construction yields:
$$m_b^* = \left\lfloor \sqrt{\frac{N}{2}} \right\rfloor \approx 0.707 \sqrt{N}, \qquad W^* = 2 m_b^* + 1 \approx \sqrt{2N}, \qquad m_g^* = \left\lceil \frac{N}{W^*} \right\rceil \approx 0.707 \sqrt{N}$$
Total steps across both phases is $\sqrt{2N} \approx 1.414 \sqrt{N}$. Note: while optimal for this two-list uniform formulation, published literature (e.g. Galbraith-Wang-Zhang 2017) demonstrates that interleaved BSGS with negation achieves $\approx 0.943 \sqrt{N}$ and block computation achieves $\approx 0.38 \sqrt{N}$ asymptotic average group operations.

### C. Tested Modular-Coordinate Obstruction (`FAIL-B03`)
Testing scalar modular projection $k \mapsto k \pmod M$:
- Sampled 2,000 random scalars on secp256k1:
  - Correlation between $y \pmod 2$ and $k \pmod 2$: $49.4\%$ (strictly random noise).
  - Correlation between $x \pmod 2$ and $k \pmod 2$: $48.9\%$ (strictly random noise).
- Finding: Direct parity predicates of affine coordinates exhibit no useful empirical correlation with scalar parity in this sample, and the prime-order group provides no proper subgroup projections. This observation records an empirical dead end for direct affine coordinate parity, leaving the broader representation family open for non-trivial modular relations.

### D. The Boundary-Normalization Hypothesis
Reflecting the core Lab K kernel progression:
- Cycle 1: $(x, y) \to x$ (eliminate sign from baby table).
- Cycle 3: affine sequence $\to$ projective differential sequence in giant steps.
- Cycle 4: bilateral elimination of $Y$ from both sides, pushing $K$ modular inversions $\to$ 1 batched inversion.
- **Preregistered Hypothesis (`H-METH-BOUNDARY-NORM`):**
  > *When an exact search condition is invariant under some internal coordinate, retain that coordinate only where required for initialization, collision resolution, or final verification; evolve the bulk computation in a cheaper reduced representation.*

---

## 3. Quantitative Tournament Results

Evaluated across the 5 frozen quantiles ($10\%, 25\%, 50\%, 75\%, 90\%$) for $N \in [16, 65536]$:

| $N$ | Baby Std (ms) | Baby Dual4 (ms) | **Baby Speedup** | Cold Std (ms) | Cold Dual4 (ms) | **Cold Speedup** | Kangaroo (ms) | **Speedup vs Kang** |
|---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 16 | 0.40ms | 0.14ms | 2.8× | 1.30ms | 1.21ms | 1.07× | 7.02ms | 5.6× |
| 64 | 0.93ms | 0.29ms | 3.3× | 2.10ms | 1.38ms | 1.52× | 10.63ms | 7.5× |
| 256 | 2.01ms | 0.33ms | 6.2× | 3.69ms | 1.48ms | 2.50× | 16.23ms | 10.9× |
| 1,024 | 4.16ms | 0.39ms | 10.6× | 6.93ms | 1.60ms | 4.34× | 27.19ms | 16.7× |
| 4,096 | 8.51ms | 0.55ms | 15.6× | 13.41ms | 2.08ms | 6.44× | 50.24ms | 23.6× |
| 16,384 | 17.14ms | 0.84ms | 20.5× | 26.32ms | 2.42ms | 10.89× | 101.09ms | 39.8× |
| 65,536 | 34.56ms | 1.42ms | **24.3×** | 52.13ms | 3.35ms | **15.58×** | 202.78ms | **55.3×** |

---

## 4. Novelty & Governance Status
- Preregistered Hypothesis: `H-DISC-04`
- Status: `PASSED`
- Novelty Classification: `KNOWN_COMPOSITION`
- Obstruction Cataloged: `FAIL-B03-TESTED-MODULAR-OBSTRUCTION`
- Methodology Hypothesis: `H-METH-BOUNDARY-NORM` (Boundary-Normalization Hypothesis)
