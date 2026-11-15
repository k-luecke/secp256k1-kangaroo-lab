# Empirical Findings: Ubuntu 13.10 Saucy Early-Boot RNG Metadata Diversity

## Executive Summary

This investigation tested the structural reproducibility and event-topology stability of early-boot entropy in the canonical Ubuntu 13.10 (Saucy Salamander) desktop AMD64 release prior to a controlled `/dev/urandom` read.

Strict safety constraints were maintained throughout:
- No internal RNG pool state words were read, stored, or reconstructed.
- No entropy payload bytes or cycle-counter low bits were harvested.
- No wallet seeds, private keys, or secret data were generated or modeled.
- Tracing was strictly confined to hardware event metadata (monotonic timestamps, IRQ numbers, CPU ID, subsystem call counts, and entropy accounting levels).

---

## 1. Artifact Facts

1. **Canonical Ubuntu 13.10 Desktop AMD64 ISO**:
   - SHA-256: `369a1f604df30e097f063829b27c39941a26e5771c53b35aa9ea0e0e0abb3a56`
   - Verified against Ubuntu's published release manifests and CD-image RSA signature.
2. **Squashfs Root Filesystem (`casper/filesystem.squashfs`)**:
   - SHA-256: `58ae7c8ec7c71510fde7899c5cb334829c5e32361d35e42e734edd0a42c172cc`
   - Confirmed: Contains `/var/lib/urandom/` as an empty directory.
   - Confirmed: `/var/lib/urandom/random-seed` is **completely absent**.
   - Conclusion: The retained fixed-saved-seed hypothesis remains **falsified**.
3. **Linux Kernel v3.11 RNG Mechanics (`drivers/char/random.c`)**:
   - Early boot initializes `input_pool` and `nonblocking_pool` via `init_std_data()`.
   - Interrupts feed per-CPU `fast_pool` structures, accumulating 4 32-bit words mixed via a simplified polynomial.
   - Fast-pool promotion into `input_pool` occurs every 64 interrupts or upon timer expirations (`now - fast_pool->last > HZ`).
   - `nonblocking_pool` initialization requires transfers from `input_pool` triggered by `urandom_read()` or early daemon entropy requests.

---

## 2. Emulator / VM Observations

A total of 215 controlled VM boots across three distinct experimental regimes were captured and analyzed:

| Metric | Regime A (Frozen VM Clock) | Regime B (Perturbations) | Regime C (Host Scheduling Jitter) |
| :--- | :--- | :--- | :--- |
| **Total Boots Analyzed** | 100 | 15 | 100 |
| **Machine Configuration** | Frozen (`-smp 1 -rtc base=utc,clock=vm`) | Single-variable perturbations | Frozen config, Host RTC (`clock=host`) |
| **Time to RNG Init (ms)** | 39.12 (std=0.00) | 39.87 (std=0.41) | 35.89 (std=1.14, range 32.1-39.5) |
| **Time to First Read (ms)**| 122.79 (std=0.00) | 125.38 (std=4.55) | 111.70 (std=2.97, range 102.5-117.8) |
| **Interrupt Count to Read** | 400 (std=0.00) | 408.6 (std=14.46) | 400.8 (std=8.90, range 385-415) |
| **Unique IRQ Topologies** | **1 / 100 (1.0%)** | **12 / 15 (80.0%)** | **100 / 100 (100.0%)** |
| **IRQ Longest Common Prefix** | 400 / 400 | Median = 1.0, Min = 0 | **Median = 2, Min = 0, Max = 7** |
| **Earliest Divergence Index** | N/A (Fully identical) | Event #0 | **Event #0 (Immediate divergence)** |
| **Pairwise Edit Distance** | 0 | Median = 157 | **Median = 159 (Max = 173)** |

### Key VM Insights:
1. **Regime A (Artificial Determinism)**:
   Under QEMU's single-threaded Tiny Code Generator (TCG) with `-rtc clock=vm` and all external peripherals disabled, QEMU advances virtual time strictly in lockstep with instructions executed. Under this synthetic constraint, event order and interrupt count were completely identical across 100 runs.
2. **Regime B (Parameter Sensitivity)**:
   Modifying single hardware parameters (adding a virtual NIC, enabling USB-EHCI, scaling SMP from 1 to 2, or shifting storage timing) radically alters the IRQ distribution and device discovery events, generating distinct topological trajectories.
3. **Regime C (Ordinary Host Scheduling Jitter)**:
   When running the exact same nominal hardware configuration but exposing the VM to ordinary host thread preemption and wall-clock interrupts (`clock=host`), **100 out of 100 boots exhibited unique IRQ sequences**.
   - The Longest Common Prefix (LCP) between boot event sequences dropped to a median of **2 events**, with earliest divergence occurring immediately at Event #0.
   - The Levenshtein edit distance between event sequences across ~400 interrupts reached a median of **159**, demonstrating combinatorial interleaving between timer ticks (IRQ 0), IDE controller I/O (IRQ 14/15), and console UART (IRQ 4).

---

## 3. Historical Assumptions

- It was assumed that an operator in late 2013 running an Ubuntu 13.10 live session or freshly installed VM might have experienced a constrained, deterministic boot state.
- It was assumed that if QEMU emulation exhibited low-dimensional event topology under realistic host conditions, the search space for pre-wallet RNG states could be bounded by a compact parameter vector.

---

## 4. Inferred Conclusions & Decision Status

### Decision Rule Evaluation:
- **Condition for Promotion**: "Promote the Saucy early-entropy hypothesis only if repeated nominally identical boots show that pre-wallet RNG state variation is governed by a small, parameterizable set of variables."
- **Condition for Demotion/Demise**: "Demote/kill the hypothesis if event ordering differs substantially between boots, many independent interrupt timings vary, multiple asynchronous devices contribute unpredictably, and pre-read state fingerprints are effectively unconstrained by reproducible boot parameters."

### Verdict: **DEMOTE / KILL THE SAUCY EARLY-BOOT RECONSTRUCTION HYPOTHESIS**

1. **Immediate Combinatorial Divergence**:
   In any execution environment subject to real-world host scheduling, thread preemption, or hardware timing (Regime C), the early-boot interrupt stream is **not low-dimensional**. It does not cluster into a handful of discrete topological buckets; every single run yields a distinct sequence of hardware interrupts before userspace reaches `/dev/urandom`.
2. **Avalanche Amplification**:
   Given that prior synthetic experiments established strong cryptographic avalanche across the Linux 3.11 pool compression function (e.g., swapping two IRQs or altering interrupt cycle spacing changes >60 of 128 output bits), the presence of 100% unique IRQ trajectories with edit distances >150 means the space of plausible pre-wallet pool states is **combinatorially vast**.
3. **Non-Reconstructibility Without Physical Side-Channels**:
   Without a saved seed file (which is demonstrably absent from the canonical squashfs) and with early-boot event ordering diverging within the first three hardware interrupts, the hypothesis that an operator's early-boot state in Ubuntu 13.10 could be reconstructed or bounded to a small, tractable set of boot parameters is **empirically unsupported**.
