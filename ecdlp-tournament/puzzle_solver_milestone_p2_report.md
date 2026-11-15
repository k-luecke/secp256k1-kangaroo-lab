# Milestone P2 Report: Representation Tournament (Linear Stepping vs. BSGS)
**General Constrained-Keyspace Cryptographic Puzzle Solver**  
**Date:** October 1, 2026 | **Environment:** Python 3.14.3 (Windows 11 64-bit)  
**Ledgers:**  
- Synthetic Tournament: `puzzle_solver/ledger/p2_tournament_results.json`  
- Historical Validation: `puzzle_solver/ledger/p2_historical_validation_results.json`  
**Mirror:** `puzzle_solver\`

---

## 1. Executive Summary & Core Thesis

Milestone P2 tested the foundational transfer hypothesis of this program:

$$\boxed{\text{Reduced candidate work is valuable only after pricing the representation that enables it.}}$$

Baby-Step Giant-Step (BSGS) provides an algebraic time-memory trade-off on the elliptic curve group $(E(\mathbb{F}_p), +)$, buying an $O(\sqrt{N})$ candidate search at the explicit price of $O(\sqrt{N})$ group precomputations and table storage.

To determine whether this algebraic compression pays its own rent under honest physical accounting, the tournament benchmarked **Linear Stepping** versus **BSGS** on identical bounded intervals and verification targets, measuring separate setup, reusable setup, online search, group operations, table probes, and wall-clock times.

### Key Results
1. **The Boss-Fight Criterion:**
   $$\boxed{\text{Does the predicted }\sqrt{N}\text{ reduction in algebraic search work survive total-cost accounting?}\quad \mathbf{YES.}}$$
   At $N = 65,536$, linear stepping required $\approx 32,768$ group operations taking $4.467\text{ s}$. BSGS cold execution required only $388$ total group operations and completed in $0.0529\text{ s}$ (**$84.43\times$ speedup**). When the baby-step table was warm, online search required $131$ group operations and took $0.0178\text{ s}$ (**$250.93\times$ speedup**).
2. **Empirical Crossover Determination ($N^*$):**
   Evaluated across five frozen target quantiles (10%, 25%, 50%, 75%, 90%) plus boundary checks (0% and 100%):
   - **Broad Bracket Sweeps:**
     $$\text{Cold Crossover Bracket: } 16 < N^*_{\text{cold}} \le 32$$
     $$\text{Warm Crossover Bracket: } 8 < N^*_{\text{warm}} \le 16$$
   - **Deterministic Refinement Sweeps:**
     $$\mathbf{N^*_{\text{cold}} = 18} \quad (T_{\text{cold}} < T_{\text{linear}} \text{ for all } N \ge 18)$$
     $$\mathbf{N^*_{\text{warm}} = 9} \quad (T_{\text{warm}} < T_{\text{linear}} \text{ for all } N \ge 9)$$
3. **Three-Regime Economic Accounting ($K^*(N)$):**
   - For $N \le 8$: $K^*(N) = \infty$ (linear stepping is strictly faster; BSGS cannot amortize setup).
   - For $N \in [9, 17]$: $K^*(N) = 2$ (BSGS breaks even if the baby-step table is reused for just 2 searches).
   - For $N \ge 18$: $K^*(N) = 1$ (BSGS breaks even from a cold start on a single search).
4. **Historical Published-Puzzle Validation (16 / 16 PASS):**
   Under strict answer quarantine, BSGS was evaluated on historical Bitcoin challenge puzzles #1 through #16 where $P_{\text{target}}$ was independently published on-chain. All 16 puzzles were solved with 100% cryptographic verification and exact match against the quarantined evaluation registry.

---

## 2. Tournament Protocol & Firewall Standard

### Strict Eligibility Firewall
$$\boxed{\text{BSGS eligibility requires an independently public } P_{\text{target}}.}$$
- In secp256k1 discrete log problems, BSGS solves $P_{\text{target}} = k \cdot G$. It requires an elliptic curve group element $P_{\text{target}}$, NOT a P2PKH Hash160 address.
- Quarantined private keys must **never** manufacture $P_{\text{target}}$ for search routines.
- Therefore, the representation tournament (P2-B, P2-C) was conducted on synthetic bounded instances where $(L, R, P_{\text{target}})$ is the public specification.
- Historical validation (P2-D) was conducted exclusively on challenges where $P_{\text{target}}$ was permanently recorded on the public Bitcoin blockchain in the claiming transaction's scriptSig.

### Three-Regime Economics
- **Cold Regime:** $T_{\text{cold}} = T_{\text{baby}} + T_{\text{instance}} + T_{\text{online}}$
- **Warm Regime:** $T_{\text{warm}} = T_{\text{instance}} + T_{\text{online}}$
- **Amortized Regime ($K$ queries):** $T_{\text{amortized}}(K) = \frac{T_{\text{baby}}}{K} + T_{\text{instance}} + T_{\text{online}}$
- **Break-Even Reuse Count:** $K^*(N) = \min\{K \ge 1 : T_{\text{amortized}}(K, N) < T_{\text{linear}}(N)\}$

---

## 3. Empirical Results Ledger

### Step 1: Broad Bracket Sweep (Powers of 2)
Median wall-clock times across frozen quantiles $q \in \{0.10, 0.25, 0.50, 0.75, 0.90\}$:

| $N$ | Step Size ($m$) | Median $T_{\text{linear}}$ (s) | Median $T_{\text{cold}}$ (s) | Median $T_{\text{warm}}$ (s) | Cold Speedup | Warm Speedup | $K^*(N)$ |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2 | 2 | 0.000249 | 0.000683 | 0.000628 | 0.36x | 0.40x | $\infty$ |
| 4 | 3 | 0.000525 | 0.000915 | 0.000782 | 0.57x | 0.67x | $\infty$ |
| 8 | 3 | 0.000796 | 0.001051 | 0.000916 | 0.76x | 0.87x | $\infty$ |
| **16** | 5 | 0.001348 | 0.001396 | 0.000962 | 0.97x | **1.40x** | **2** |
| **32** | 6 | 0.002392 | 0.001581 | 0.001037 | **1.51x** | **2.31x** | **1** |
| 64 | 9 | 0.004585 | 0.002157 | 0.001165 | 2.13x | 3.94x | 1 |
| 128 | 12 | 0.009008 | 0.002806 | 0.001441 | 3.21x | 6.25x | 1 |
| 256 | 17 | 0.017680 | 0.003833 | 0.001698 | 4.61x | 10.41x | 1 |
| 512 | 23 | 0.034807 | 0.005192 | 0.002251 | 6.70x | 15.46x | 1 |
| 1,024 | 33 | 0.069666 | 0.006985 | 0.002766 | 9.97x | 25.19x | 1 |
| 2,048 | 46 | 0.138746 | 0.009671 | 0.003727 | 14.35x | 37.23x | 1 |
| 4,096 | 65 | 0.281667 | 0.013561 | 0.005015 | 20.77x | 56.17x | 1 |

---

### Step 2: Deterministic Refinement Sweeps

#### Cold Crossover Refinement in $[16, 32]$:
Evaluating all integer values in $[16, 32]$ on the 5 frozen quantiles pinpointed the transition:
- $N = 16$: $T_{\text{lin}} = 1.355\text{ ms}$, $T_{\text{cold}} = 1.463\text{ ms} \implies 0.93\times$ ($K^* = 2$)
- $N = 17$: $T_{\text{lin}} = 1.321\text{ ms}$, $T_{\text{cold}} = 1.410\text{ ms} \implies 0.94\times$ ($K^* = 2$)
- **$N = 18$**: $T_{\text{lin}} = 1.411\text{ ms}$, $T_{\text{cold}} = 1.354\text{ ms} \implies \mathbf{1.04\times}$ ($\mathbf{K^* = 1}$)
- $N = 19$: $T_{\text{lin}} = 1.475\text{ ms}$, $T_{\text{cold}} = 1.310\text{ ms} \implies 1.13\times$ ($K^* = 1$)
- $N = 20$: $T_{\text{lin}} = 1.682\text{ ms}$, $T_{\text{cold}} = 1.334\text{ ms} \implies 1.26\times$ ($K^* = 1$)

$$\mathbf{N^*_{\text{cold}} = 18}$$

#### Warm Crossover Refinement in $[8, 16]$:
Evaluating all integer values in $[8, 16]$ on the 5 frozen quantiles:
- $N = 8$: $T_{\text{lin}} = 0.819\text{ ms}$, $T_{\text{warm}} = 0.901\text{ ms} \implies 0.91\times$
- **$N = 9$**: $T_{\text{lin}} = 1.050\text{ ms}$, $T_{\text{warm}} = 0.905\text{ ms} \implies \mathbf{1.16\times}$
- $N = 10$: $T_{\text{lin}} = 0.786\text{ ms}$, $T_{\text{warm}} = 0.777\text{ ms} \implies 1.01\times$
- $N = 11$: $T_{\text{lin}} = 1.040\text{ ms}$, $T_{\text{warm}} = 0.896\text{ ms} \implies 1.16\times$
- $N = 12$: $T_{\text{lin}} = 1.101\text{ ms}$, $T_{\text{warm}} = 0.897\text{ ms} \implies 1.23\times$

$$\mathbf{N^*_{\text{warm}} = 9}$$

---

### Step 3: Scaling & Workload Law Validation

| $N$ | Step Size ($m$) | Median $T_{\text{linear}}$ (s) | Median $T_{\text{cold}}$ (s) | Median $T_{\text{warm}}$ (s) | Cold Speedup | Warm Speedup |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 8,192 | 91 | 0.587840 | 0.019069 | 0.007115 | 30.83x | 82.62x |
| 16,384 | 129 | 1.151533 | 0.026442 | 0.009176 | 43.55x | 125.50x |
| 32,768 | 182 | 2.294189 | 0.038113 | 0.012875 | 60.19x | 178.19x |
| 65,536 | 257 | 4.467444 | 0.052913 | 0.017803 | **84.43x** | **250.93x** |

---

## 4. Historical Validation Arm (Puzzles #1 through #16)

Under strict firewall conditions (the algorithm received only $L, R, P_{\text{target}}$):

| Puzzle ID | Bit Length | $N$ | $m$ | $T_{\text{cold}}$ (s) | $T_{\text{warm}}$ (s) | Status | Recovered Key |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `btc_2015_001` | 1 | 1 | 2 | 0.000181 | 0.000158 | **PASS** | `0x1` |
| `btc_2015_002` | 2 | 2 | 2 | 0.000556 | 0.000558 | **PASS** | `0x3` |
| `btc_2015_003` | 3 | 4 | 3 | 0.000708 | 0.000610 | **PASS** | `0x7` |
| `btc_2015_004` | 4 | 8 | 3 | 0.000567 | 0.000437 | **PASS** | `0x8` |
| `btc_2015_005` | 5 | 16 | 5 | 0.001020 | 0.000598 | **PASS** | `0x15` |
| `btc_2015_006` | 6 | 32 | 6 | 0.001572 | 0.000616 | **PASS** | `0x31` |
| `btc_2015_007` | 7 | 64 | 9 | 0.001694 | 0.000627 | **PASS** | `0x4c` |
| `btc_2015_008` | 8 | 128 | 12 | 0.003051 | 0.000664 | **PASS** | `0xe0` |
| `btc_2015_009` | 9 | 256 | 17 | 0.004440 | 0.000670 | **PASS** | `0x1d3` |
| `btc_2015_010` | 10 | 512 | 23 | 0.003471 | 0.000658 | **PASS** | `0x202` |
| `btc_2015_011` | 11 | 1,024 | 33 | 0.005278 | 0.000667 | **PASS** | `0x483` |
| `btc_2015_012` | 12 | 2,048 | 46 | 0.008709 | 0.001955 | **PASS** | `0xa7b` |
| `btc_2015_013` | 13 | 4,096 | 65 | 0.011545 | 0.002652 | **PASS** | `0x1460` |
| `btc_2015_014` | 14 | 8,192 | 91 | 0.016155 | 0.004010 | **PASS** | `0x2930` |
| `btc_2015_015` | 15 | 16,384 | 129 | 0.028948 | 0.012148 | **PASS** | `0x68f3` |
| `btc_2015_016` | 16 | 32,768 | 182 | 0.039247 | 0.014569 | **PASS** | `0xc936` |
| **Total / Overall** | **1..16** | **65,535** | — | **0.1311s** | **0.0416s** | **16 / 16 PASS** | — |

---

## 5. File Manifest & Google Drive Synchronization

All 26 files under `puzzle_solver/` have been mirrored to `puzzle_solver\` and verified via automated SHA-256 hash comparison (`All hashes match: True`):

```
puzzle_solver/
├── baselines/
│   └── sequential_scan.py                      (P1 linear baseline scanner)
├── benchmarks/
│   ├── solver1_baseline.py                     (P1 benchmark runner)
│   ├── solver2_historical_validation.py        (P2-D historical validation runner)
│   └── tournament_p2.py                        (P2 representation tournament runner)
├── ledger/
│   ├── p1_baseline_results.json                (P1 baseline ledger)
│   ├── p2_historical_validation_results.json   (P2 historical validation ledger)
│   └── p2_tournament_results.json              (P2 synthetic tournament ledger)
├── representations/
│   └── bsgs.py                                 (BSGSSolver, BabyStepTable, LinearDlogScanner)
├── specs/
│   └── schema.py                               (Machine-readable specification schema)
├── targets/
│   └── puzzle_registry.py                      (Historical challenge registry + quarantined truth)
├── tests/
│   ├── test_baselines.py                       (Linear scanner unit tests)
│   ├── test_bsgs.py                            (BSGS boundary & correctness unit tests)
│   └── test_verification.py                    (secp256k1 & Base58Check unit tests)
└── verification/
    ├── address.py                              (Base58Check, Hash160, pubkey serialization)
    └── secp256k1.py                            (Exact Jacobian projective point arithmetic)
```
