# Discovery Cycle 6 Report: Super-Batching, Progressive Normalization & Tested Multi-Giant Wavefront Bottleneck
**Algorithm Discovery Program | Lab B: Bounded secp256k1**  
**Date:** October 2026  
**Status:** FROZEN  
**Hypotheses:**  
- `H-DISC-06` (PASSED): Super-batching differential BSGS ($B=128$) reduces per-step inversion overhead to $0.78M$, achieving a $1.63\times$ speedup over the project's GWZ-2017 reproduction and $16.03\times$ over standard BSGS at $N=65,536$.
- `FAIL-B04` (TESTED STRUCTURAL BOTTLENECK): Under the tested 2D differential recurrence construction, multi-dimensional giant grids require buffering an $O(W_1)$ projective point wavefront, increasing memory requirements compared to the 1D differential BSGS implementation.
**Target Ledger:** `cycle6_superbatch_tournament_results.json`

---

## 1. Executive Summary

In Discovery Cycle 6, we investigated the mathematical and computational limits of boundary normalization on the active champion, Dual-End Projective Differential BSGS.

Key discoveries:
1. **Inversion Amortization Boundary ($B^* = 128$):** By expanding the Montgomery simultaneous inversion window from $B=32$ to $B=128$, the field inversion rent is amortized from $3.1M$ down to $0.78M$ per giant step. At $N=65,536$, cold wall-clock time drops to **$3.24$ ms**, achieving a **$1.63\times$ speedup** over the project's GWZ-2017 reproduction ($5.30$ ms) and **$16.03\times$** over textbook BSGS ($51.98$ ms).
2. **Quantization Latency Tradeoff:** Micro-benchmarking identified the quantization tradeoff: while large batches amortize inversion, they quantize collision checks to intervals of $B$. For shallow targets ($q=0.10$), early batch termination benefits from smaller initial windows ($B_0 \le 32$), whereas deep targets ($q \ge 0.75$) benefit maximally from $B=128$.
3. **Tested Wavefront Memory Bottleneck (`FAIL-B04`):** Analysis of the Bernstein-Lange (2013) multi-giant representation revealed that stepping differentially in 2D ($P_{i_1, i_2+1} = 2 P_{i_1, i_2} - P_{i_1, i_2-1}$) under the tested recurrence requires neighboring points from the preceding row, forcing the solver to buffer an active projective point wavefront of size $O(W_1) \sim O(N^{1/4})$, increasing stepping memory compared to 1D differential BSGS.

---

## 2. Quantitative Tournament Results

Evaluated across the 5 frozen quantiles ($10\%, 25\%, 50\%, 75\%, 90\%$) for $N \in [16, 65536]$:

| $N$ | Standard BSGS (ms) | Pollard Kangaroo (ms) | GWZ-2017 Repro (ms) | Diff $B=32$ (ms) | Diff $B=64$ (ms) | Diff $B=128$ (ms) | **Frontier Speedup $S_{\text{frontier}}$** | **Speedup vs Standard** | **Speedup vs Kangaroo** |
|---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 16 | 1.31ms | 0.45ms | 1.11ms | 1.22ms | 1.21ms | 1.24ms | 0.90× | 1.06× | 0.36× |
| 64 | 2.08ms | 0.95ms | 1.14ms | 1.39ms | 1.44ms | 1.42ms | 0.80× | 1.46× | 0.67× |
| 256 | 3.68ms | 1.88ms | 1.26ms | 1.48ms | 1.48ms | 1.48ms | 0.85× | 2.49× | 1.27× |
| 1,024 | 6.86ms | 3.92ms | 1.56ms | 1.61ms | 1.62ms | 1.60ms | 0.98× | 4.29× | 2.45× |
| 4,096 | 13.37ms | 9.40ms | 2.11ms | 2.09ms | 2.12ms | 2.13ms | 0.99× | 6.28× | 4.41× |
| 16,384 | 26.14ms | 36.80ms | 3.40ms | 2.42ms | 2.54ms | 2.46ms | **1.38×** | **10.63×** | **14.96×** |
| 65,536 | 51.98ms | 182.31ms | 5.30ms | 3.34ms | 3.37ms | **3.24ms** | **1.63×** | **16.03×** | **56.24×** |

- **Headline Metric ($S_{\text{frontier}}$):** $S_{\text{frontier}} = T_{\text{GWZ-2017 repro}} / T_{\text{Diff } B=128} = \mathbf{1.63\times}$ at $N=65,536$.
- **Historical Lineage Telemetry:** Milestone P1 linear scan equivalent speedup: $\approx 1,440\times$.
- **Held-Out Generalization:** Evaluated on 10 independent pseudo-random seeds uniformly sampled from $[L, R]$; achieved 100% blind key recovery with median cold time **$3.29$ ms** vs GWZ-2017 reproduction **$5.34$ ms** ($1.62\times$ frontier speedup).

---

## 3. Tested Structural Bottleneck Certificate (`FAIL-B04`)

- **Failure ID:** `FAIL-B04`
- **Title:** Tested Wavefront Memory Bottleneck for 2D Differential Grids
- **Statement:** Under the tested 2D differential recurrence construction, advancing multi-dimensional giant grids without redundant point multiplications requires buffering at least $\prod_{k=1}^{d-1} W_k$ projective points along the stepping wavefront.
- **Consequence:** In our implementation, while 1D differential BSGS operates in strictly 2-point stepping memory, the tested multi-dimensional grid incurs higher buffer overhead for interval sizes $N \le 2^{32}$.

---

## 4. Novelty & Governance Classification

- **Preregistration Hash:** `f6ca0bcfd02b03668196e4021828c5c98c4da9691e3a8c991a5c48743554905c`
- **Result Status:** `PASSED`
- **Novelty Classification:** `KNOWN_COMPOSITION` + `TESTED_STRUCTURAL_BOTTLENECK`
- **Verified Claim:** `CLAIM-B-11`: Expanding the boundary normalization batch size to $B=128$ achieves $1.63\times$ speedup over the project's GWZ-2017 reproduction at $N=65,536$ while documenting that the tested 2D differential multi-giant grid incurs an $O(W_1)$ projective wavefront buffer (`FAIL-B04`).
