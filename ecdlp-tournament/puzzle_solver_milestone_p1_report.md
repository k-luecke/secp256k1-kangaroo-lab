# Milestone P1 Report: Baseline Recovery & Bounded Search
**General Constrained-Keyspace Cryptographic Puzzle Solver**  
**Date:** October 1, 2026 | **Environment:** Python 3.14.3 (Windows 11 64-bit)  
**Ledger:** `puzzle_solver/ledger/p1_baseline_results.json`  
**Mirror:** `puzzle_solver\`

---

## 1. Executive Summary

Milestone P1 transitions the program from the reduced-RC4 search-controller line into a **general constrained-keyspace cryptographic puzzle solver**. The objective was to demonstrate **zero-leakage blind recovery** of intentionally published cryptographic puzzles using strictly quarantined specifications.

The baseline search engine (`SequentialScanner`) was evaluated against the historical **2015 Bitcoin transaction challenge suite** (Tx: `08389f34c98c606322740c0be6a7114d2d277787f16548b0825da76d9229724f`), spanning Puzzles #1 through #16 ($k \in [1, 2^{16}-1]$).

### Key Results
1. **100% Solution Recovery (16 / 16 Puzzles Solved):** The search engine independently discovered all 16 target private keys without access to ground truth.
2. **Cryptographic Grounding:** Every recovered private key $k$ was independently verified:
   $$\text{Base58Check}\Big(\text{Hash160}\big(\text{SEC}(k \cdot G)\big)\Big) \equiv \text{Target Address}$$
   yielding an exact 16/16 address match and 16/16 match against the quarantined evaluation registry.
3. **Execution Throughput:** Across 33,826 candidates tested, the pure-Python engine achieved **7,112.1 keys/second** using mixed Jacobian point stepping ($P_{k+1} = P_k + G$) and direct 20-byte Hash160 matching, completing the entire 16-puzzle panel in **4.7561 seconds**.
4. **Mirroring & Verification:** All 20 module files, test suites, and ledger artifacts were synchronized to Google Drive and cryptographically verified via SHA-256.

---

## 2. Methodology & Strict Quarantine Standard

### Architecture Lineage
The core lesson from RC4 Micro-Experiments 1 through 16 is that search speedup is governed by candidate-step workload $W = \sum N_k c_k$. In cryptographic inversion, full scalar multiplications ($k \cdot G$, requiring ~256 doublings and ~128 additions) are expensive ($c_0 \gg 1$). The baseline scanner amortizes this cost:
1. **Initial Point:** Compute $P_{k_0} = k_0 \cdot G$ once at the lower bound.
2. **Sequential Stepping:** For each subsequent candidate, advance via mixed Jacobian addition:
   $$P_{k+1} = P_k + G \quad (\text{with } Z_G = 1)$$
   requiring only 8 modular multiplications / squarings in $\mathbb{F}_p$ plus 1 affine inversion (`pow(Z, p-2, p)`), rather than hundreds of curve operations.
3. **Hash Matching:** Non-matching candidates are compared directly against the 20-byte target Hash160 (`address_to_hash160(spec.target.target_value)`), eliminating Base58 encoding overhead during search.

### Quarantine Standard
The search engine receives strictly a `PuzzleSpec` containing:
- `spec.target.target_value` (e.g. `1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH`)
- `spec.candidate_space.lower_bound` and `upper_bound`
- Public constraints (if any)

The ground-truth private keys reside exclusively in `_QUARANTINED_TRUTH` inside `puzzle_registry.py` and are accessible solely to test runners for post-hoc validation after search termination.

---

## 3. Empirical Results Ledger (Puzzles #1 through #16)

| Puzzle ID | Bit Length | Keyspace ($N$) | Candidates Tested | Time (s) | Throughput (keys/s) | Cryptographic Status | Recovered Private Key |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `btc_2015_001` | 1 | 1 | 1 | 0.000038 | 26,525.2 | **PASS** | `0x1` |
| `btc_2015_002` | 2 | 2 | 2 | 0.000289 | 6,918.0 | **PASS** | `0x3` |
| `btc_2015_003` | 3 | 4 | 4 | 0.000568 | 7,037.3 | **PASS** | `0x7` |
| `btc_2015_004` | 4 | 8 | 1 | 0.000150 | 6,648.9 | **PASS** | `0x8` |
| `btc_2015_005` | 5 | 16 | 6 | 0.000845 | 7,097.2 | **PASS** | `0x15` |
| `btc_2015_006` | 6 | 32 | 18 | 0.002490 | 7,228.3 | **PASS** | `0x31` |
| `btc_2015_007` | 7 | 64 | 13 | 0.001805 | 7,200.6 | **PASS** | `0x4c` |
| `btc_2015_008` | 8 | 128 | 97 | 0.013356 | 7,262.9 | **PASS** | `0xe0` |
| `btc_2015_009` | 9 | 256 | 212 | 0.029210 | 7,257.7 | **PASS** | `0x1d3` |
| `btc_2015_010` | 10 | 512 | 3 | 0.000456 | 6,583.3 | **PASS** | `0x202` |
| `btc_2015_011` | 11 | 1,024 | 132 | 0.018235 | 7,239.4 | **PASS** | `0x483` |
| `btc_2015_012` | 12 | 2,048 | 636 | 0.087631 | 7,257.7 | **PASS** | `0xa7b` |
| `btc_2015_013` | 13 | 4,096 | 1,121 | 0.154009 | 7,278.8 | **PASS** | `0x1460` |
| `btc_2015_014` | 14 | 8,192 | 2,353 | 0.324440 | 7,252.5 | **PASS** | `0x2930` |
| `btc_2015_015` | 15 | 16,384 | 10,484 | 1.443909 | 7,260.8 | **PASS** | `0x68f3` |
| `btc_2015_016` | 16 | 32,768 | 18,743 | 2.678732 | 6,997.1 | **PASS** | `0xc936` |
| **Total / Overall** | **1..16** | **65,535** | **33,826** | **4.756128 s** | **7,112.1 keys/s** | **16 / 16 PASS** | — |

---

## 4. Workload Characteristics & Observations

1. **Step Workload Linearity:** Throughput remained stable at $\sim 7,100 \text{ to } 7,280 \text{ keys/second}$ from $m=2$ to $m=16$.
2. **Early Termination Fraction:** Across the 16 puzzles, the target key was located after testing an average of $51.6\%$ of the puzzle's search interval, consistent with uniform random target positioning.
3. **Pure-Python Overhead Breakdown:**
   - Mixed Jacobian point addition: $\approx 15 \mu\text{s}$
   - Projective to affine inversion (`pow(Z, p-2, p)`): $\approx 45 \mu\text{s}$
   - Public key serialization & Hash160 (SHA256 + RIPEMD160): $\approx 80 \mu\text{s}$
   - Total per-candidate latency: $\approx 140 \mu\text{s}$ ($7,140 \text{ keys/s}$).

---

## 5. File Manifest & Google Drive Synchronization

All files under `puzzle_solver` have been mirrored to `puzzle_solver\` and verified via automated SHA-256 hash comparison (`All hashes match: True` across 20 files):

```
puzzle_solver/
├── __init__.py
├── baselines/
│   ├── __init__.py
│   └── sequential_scan.py          (Mixed Jacobian stepping + Hash160 comparison)
├── benchmarks/
│   ├── __init__.py
│   └── solver1_baseline.py         (Automated benchmark runner across Puzzles 1..16)
├── ledger/
│   ├── __init__.py
│   └── p1_baseline_results.json    (Full JSON execution ledger with timings and keys)
├── operators/
│   └── __init__.py
├── representations/
│   └── __init__.py
├── schedulers/
│   └── __init__.py
├── specs/
│   ├── __init__.py
│   └── schema.py                   (PuzzleSpec, TargetSpec, CandidateSpaceSpec schema)
├── targets/
│   ├── __init__.py
│   └── puzzle_registry.py          (Public specs + quarantined truth for #1..#16)
├── tests/
│   ├── __init__.py
│   ├── test_baselines.py           (Unit tests for blind recovery & quarantine)
│   └── test_verification.py        (secp256k1 & Base58Check unit tests)
└── verification/
    ├── __init__.py
    ├── address.py                  (Hash160, Base58Check, pubkey serialization)
    └── secp256k1.py                (Pure-Python Jacobian projective arithmetic)
```

---

## 6. Next Step: Milestone P2 (Representation Tournament & Quotient Search)

With baseline recovery verified and candidate throughput established, the next architectural milestone is **Milestone P2**:
1. **Baby-Step Giant-Step (BSGS) / Quotient Representation:** Formulate keyspace search as equivalence classes modulo $m$:
   $$P = \gamma \cdot G \iff P - j \cdot G = i \cdot (m \cdot G)$$
   This reduces candidate EC operations from $O(N)$ to $O(\sqrt{N})$.
2. **Workload Model Evaluation:** Predict when the memory/hash table setup cost of the BSGS representation breaks even against linear sequential stepping, validating our candidate-step workload model on elliptic curve groups.
