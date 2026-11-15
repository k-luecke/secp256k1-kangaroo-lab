# secp256k1-kangaroo-lab

Consolidated benchmarking, representation-tournament, and protocol-verification repository for bounded elliptic-curve discrete logarithm (`secp256k1`) and historical key-generation experiments.

Developed at [Driftbound Labs](https://driftboundlabs.com).

---

## Repository Structure & Empirical Outcomes

| Directory | Scope | Outcome |
|---|---|---|
| [`gpu-kangaroo/`](gpu-kangaroo/) | OpenCL decoupled Pollard's Kangaroo (`secp256k1` Montgomery batch inversion + distinguished-point collision search) | **Supported (engineering speedup only):** Verified blind & historical recovery on solved Bitcoin Puzzles `#40`–`#44` (`49.3M` group ops across `25.8T` interval keys in `52.4 s` total on consumer Vega 7 iGPU). Asymptotic complexity remains strictly classical $\mathcal{O}(\sqrt{N})$. |
| [`ecdlp-tournament/`](ecdlp-tournament/) | Modular ECDLP solver (`puzzle_solver/`) & Discovery Cycles 1–16 (`discovery-cycles/`) | **Not supported (asymptotic / sub-constant superiority over classical Kangaroo):** Evaluates `x`-only differential BSGS, GWZ-2017 interleaved BSGS, GLV endomorphism quotient walks, and superbatch Montgomery ladders under matched operation counts. Documents why sign ambiguity and endomorphism non-locality fail to beat standard distinguished-point Pollard Kangaroo on bounded intervals. |
| [`regtest-verifier/`](regtest-verifier/) | BIP34 coinbase & `SHA-256d` C/Python block-template harness | **Supported (protocol conformance):** Local `bitcoind -regtest` template construction and double-SHA-256 verification. |
| [`entropy-audit/`](entropy-audit/) | Ubuntu 13.10 (`saucy`) QEMU `/dev/urandom` early-boot entropy harness | **Mixed:** Quantifies kernel entropy-pool seeding variance across cold QEMU boots for historical PRNG audit baselines. |

---

## Quick Verification

```bash
# 1. Verify OpenCL component SHA-256 hashes and secp256k1 / Base58Check invariants (Puzzles #40-#44)
cd gpu-kangaroo && python3 verify_puzzle_benchmark_release.py

# 2. Run modular ECDLP tournament unit tests
cd ../ecdlp-tournament && python3 -m unittest discover -s puzzle_solver/tests -t .
```

---

## Non-Claims

- No sub-exponential or sub-$\sqrt{N}$ algorithm for `secp256k1` discrete logarithms is claimed or achieved; [`ecdlp-tournament/`](ecdlp-tournament/) explicitly preserves the falsified algebraic and representation hypotheses alongside the classical GPU baseline.
- Only publicly solved historical benchmark keys (`#40`–`#44`) and local `regtest` fixtures are evaluated.

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
