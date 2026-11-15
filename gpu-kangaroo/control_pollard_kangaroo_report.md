# Control Branch Report: Pollard's Kangaroo (Lambda) Memory-Efficient Baseline
**Algorithm Discovery Program | Lab B: Bounded secp256k1**  
**Date:** October 2026  
**Status:** FROZEN  
**Target Ledger:** `puzzle_solver/ledger/control_kangaroo_results.json`

---

## 1. Executive Summary

Pollard's Kangaroo (Lambda) algorithm was established as the external $O(1)$-memory baseline for bounded secp256k1 discrete logarithm search ($P_{\text{target}} = k G$ for $k \in [L, R]$). Prior tournament results (Milestone P2) demonstrated that Baby-Step Giant-Step (BSGS) achieves substantial algebraic speedup ($84.4\times$ cold at $N=65,536$) by paying an $O(\sqrt{N})$ memory rent. To rigorously calibrate candidate representations against memory-efficient baselines, Pollard's Kangaroo was calibrated, verified, and benchmarked across the frozen quantile panel ($N \in [16, 65536]$).

Key findings:
1. **$O(1)$ Memory Storage:** Stored distinguished points remained strictly bounded between $17$ and $39$ points across all tested keyspace sizes up to $N = 65,536$, confirming genuine $O(1)$ storage complexity.
2. **Algebraic Crossover vs. Linear Stepping:** Pollard's Kangaroo breaks even against linear stepping between $N = 64$ and $N = 256$ ($N^*_{\text{kang}} \approx 180$). At $N = 65,536$, Kangaroo achieves a **$23.01\times$ speedup** over linear stepping ($0.2028$s vs $4.6668$s).
3. **Time-Memory Pareto Frontier:** While Kangaroo outperforms linear search by over an order of magnitude at large $N$, BSGS and $X$-Only BSGS remain $\approx 5.4\times$ faster in wall-clock time due to deterministic stepping and direct hash table lookups, establishing the empirical Pareto frontier between $O(1)$ memory and $O(\sqrt{N})$ memory.

---

## 2. Experimental Design & Jump Calibration

### A. Mathematical Formulation
- Interval: $[L, R]$, keyspace size $N = R - L + 1$, target $k \in [L, R]$.
- Optimal mean jump size: $\mu = \max(2, \lfloor \frac{1}{2} \sqrt{N} \rfloor)$.
- Jump set: $r = 16$ jumps uniformly distributed across $[1, 2\mu - 1]$ with mean exactly $\mu$ and $\gcd = 1$.
- Distinguished point condition: $x(P) \pmod{2^d} = 0$, where $d = \max(1, \min(20, \lfloor \log_2(\mu / 4) \rfloor))$. This maintains an expected trap count of $\approx 16$ to $32$ distinguished points regardless of $N$.
- Tame kangaroo walk: Initiates at $R$ and advances $M_T = \lfloor 3.8 \sqrt{N} \rfloor + 16$ steps.
- Wild kangaroo walk: Initiates at $P_{\text{target}}$ and advances until coalescence or horizon overshoot ($D_W > D_T + 2\mu$).

---

## 3. Quantitative Results

Evaluated across the 5 frozen quantiles ($10\%, 25\%, 50\%, 75\%, 90\%$) for $N \in [16, 65536]$:

| $N$ | Median Linear (s) | Median Kangaroo (s) | DPs Stored | Median Group Ops | Speedup vs Linear | BSGS Cold (s) | X-Only Cold (s) |
|---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 16 | 0.0013s | 0.0070s | 17 | 69 | 0.19× | 0.0013s | 0.0009s |
| 64 | 0.0046s | 0.0106s | 21 | 117 | 0.43× | 0.0021s | 0.0015s |
| 256 | 0.0177s | 0.0162s | 39 | 197 | 1.09× | 0.0038s | 0.0026s |
| 1,024 | 0.0716s | 0.0272s | 39 | 353 | 2.63× | 0.0071s | 0.0048s |
| 4,096 | 0.2796s | 0.0502s | 32 | 685 | 5.57× | 0.0136s | 0.0091s |
| 16,384 | 1.1441s | 0.1011s | 33 | 1,373 | 11.32× | 0.0270s | 0.0180s |
| 65,536 | 4.6668s | 0.2028s | 27 | 2,651 | **23.01×** | 0.0540s | 0.0374s |

---

## 4. Key Takeaways

1. **Memory Invariance:** Stored points remained $O(1)$ ($17 \le |\text{DP}| \le 39$) while runtime scaled precisely as $O(\sqrt{N})$.
2. **Pareto Trade-Off:** 
   - When memory is constrained to $O(1)$, Pollard's Kangaroo provides $23\times$ speedup over linear stepping.
   - When memory is available ($O(\sqrt{N})$), BSGS provides a further $5.4\times$ speedup over Kangaroo.
