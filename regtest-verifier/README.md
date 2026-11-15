# Frankenstein v0.8 — Bitcoin regtest-first prototype

## Scope

- Reuses v0.7 compiled C SHA-256d nonce scanner, with a **critical correction**: Bitcoin proof-of-work compares the raw double-SHA256 digest as a **little-endian 256-bit integer**. v0.6/v0.7 scanner target comparisons used the wrong orientation; do not deploy them for real Bitcoin work.
- Assembles a BIP34 coinbase (block-height scriptSig), coinbase transaction, Merkle root, header and an empty block, using selected values from `getblocktemplate`.
- Decodes 256-bit compact `nBits` and checks the native found digest with independent Python `hashlib`.
- `--submit` can call `submitblock`, but **only** after `getblockchaininfo` confirms `regtest`. No submission to mainnet or testnet is allowed.
- `--regtest-rpc` accepts local loopback RPC only; credentials are passed through environment variables.

## Test offline

```bash
python test_v08.py
python bitcoin_regtest.py --template sample_regtest_template.json --start 0 --count 1000
```

On Linux, the script compiles the C library on first use using GCC. On Windows, compile `frankenstein_sha256d.c` to `frankenstein.dll` with a compatible C compiler, for example using GCC/MinGW:

```powershell
 gcc -O3 -std=c11 -shared frankenstein_sha256d.c -o frankenstein.dll
```

## Optional local Bitcoin Core regtest

Start Bitcoin Core with RPC enabled **on a private local regtest instance**, then set `BTC_RPC_USER` and `BTC_RPC_PASSWORD` in your shell. The following performs a small nonce scan and only submits a candidate if explicitly requested:

```bash
python bitcoin_regtest.py --regtest-rpc http://127.0.0.1:18443/ --count 100000 --submit
```

`getblocktemplate` RPC on regtest may require a connected peer, depending on Bitcoin Core configuration/version. Regtest integration and `submitblock` have **not been tested here**: no `bitcoind` binary or running node was present. The offline sample template is illustrative, **not a promise of a consensus-valid live block**.

## Deliberate limitations

- Empty blocks only; doesn't include template transactions, transaction fees, SegWit witness transactions, or witness commitments.
- `OP_TRUE` coinbase payout is **regtest-only** and should never be used to mine real BTC rewards. No wallet integration.
- Template could become stale; no job refresh, time rolling, extranonce rolling, durable ledger, or long-running mining loop yet.
- Native C remains a scalar CPU backend; AMD OpenCL and optimized SIMD are future steps.
- Offline validation covers hashing, basic block assembly, nonce range and target handling, but cannot replace consensus checks by a real node.

## Next gates

1. Actual Bitcoin Core regtest block acceptance and 100+ submitted regression blocks.
2. Correct witness-commitment handling, payout scripts and template transaction selection.
3. Durably journal work ranges and stale-tip detection, then introduce long-running loops.
4. GPU backend only after identical cross-backend Bitcoin-oriented proof-of-work validation.
