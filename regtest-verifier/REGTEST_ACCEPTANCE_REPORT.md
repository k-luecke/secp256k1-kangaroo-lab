# Frankenstein Miner v0.8 — Regtest Acceptance Report
**Date:** October 8, 2026  
**Platform:** Windows 11 (MSVC x64 native compilation)  
**Node:** Bitcoin Core v28.1 (`bitcoind.exe` portable win64)  
**Network:** Private Local `regtest` (`chain = regtest`, RPC loopback port 18443)

---

## 1. Setup & Environment
- **Node binaries:** Official Bitcoin Core 28.1 portable release downloaded and SHA-256 verified:
  - Checksum: `2d636ad562b347c96d36870d6ed810f4a364f446ca208258299f41048b35eab0`
  - Location: `bitcoin_core/bitcoin-28.1/bin/` (`bitcoind.exe`, `bitcoin-cli.exe`)
- **Node config:** Dedicated local datadir `regtest_data/` with `bitcoin.conf` (credentials configured in file, avoiding command-line process exposure).
- **Frankenstein Core:** Native C SHA-256d scanner compiled to `frankenstein.dll` via MSVC (`/O2`, exported symbols `franken_scan07`, `franken_scan06`, `franken_hash`).

---

## 2. Testing & Consensus Bug Resolution

### Initial Submission Attempt (Height 1)
- **Node response:** `submitblock result: bad-cb-height`
- **Root Cause Discovered:**
  - In `bitcoin_regtest.py`, BIP34 coinbase serialization initially encoded heights using `push(script_num(height))` uniformly.
  - Per Bitcoin Core consensus (`CScript::operator<<(int64_t)` and BIP34):
    - Heights `1` through `16` MUST be encoded as single-byte opcodes `OP_1` through `OP_16` (`0x51` .. `0x60`).
    - Height `0` is encoded as `OP_0` (`0x00`).
    - Heights `>= 17` are encoded as push-data chunks (`len + script_num(height)`).
- **Resolution:**
  Implemented `bip34_height(n)` in `bitcoin_regtest.py` and updated unit tests in `test_v08.py`.

---

## 3. Live Regtest Verification Results

### Unit & Regression Suite (`test_v08.py`)
- `test_compact`: **PASSED**
- `test_genesis_hash`: **PASSED**
- `test_coinbase_height` (testing 1..16, 17, 128, 500000): **PASSED**
- `test_low_target`: **PASSED**
- `test_block_and_native`: **PASSED**
- `test_randomized_bitcoin_target_endianness` (96 randomized SHA-256d target checks): **PASSED**

### Live Mining Sequence (Blocks 3 through 20)
All blocks were produced dynamically via `getblocktemplate`, solved by `frankenstein.dll`, and submitted via `submitblock`:
- **Height 3:** `0946c5b8c1fd8c693b210361177b350629f6363d09045579262ee8676cb3e124` — **ACCEPTED**
- **Height 4:** `775e26e104ff9c3125d6d8087c0cb1eac2c0ad49cfbb099853d52c01e896cae6` — **ACCEPTED**
- **Height 5:** `5a6d13d82dba1a3f...` — **ACCEPTED**
- **Height 6:** `511f2bbe2935e13b...` — **ACCEPTED**
- **Height 7:** `244576ec4631f5e8...` — **ACCEPTED**
- **Height 8:** `1f9c557418b5e3ba...` — **ACCEPTED**
- **Height 9:** `70a81933488f0f38...` — **ACCEPTED**
- **Height 10:** `576da83be83ff5df...` — **ACCEPTED**
- **Height 11:** `15279e73ea1d37aa...` — **ACCEPTED**
- **Height 12:** `0caab04dd5190df7...` — **ACCEPTED**
- **Height 13:** `10f37ca072335286...` — **ACCEPTED**
- **Height 14:** `5da0f1d6fb98ef05...` — **ACCEPTED**
- **Height 15:** `4ef4701a1d510032...` — **ACCEPTED**
- **Height 16:** `56b61792c3be2995...` — **ACCEPTED**
- **Height 17:** `5303789a3c3b39a7...` (BIP34 opcode-to-pushdata transition boundary) — **ACCEPTED**
- **Height 18:** `431809c1af28fc43...` — **ACCEPTED**
- **Height 19:** `29cf9bd2fe40a115...` — **ACCEPTED**
- **Height 20:** `68ae24b275a0a25e...` — **ACCEPTED**

Current Bitcoin Core chain state:
- `blocks`: 20
- `headers`: 20
- `bestblockhash`: `68ae24b275a0a25ee8e0192a54fb22c1db0fa3dd41a9bc34b3e51240c5f21ee4`
- `initialblockdownload`: false

---

## 4. Status Against Milestones
- [x] Windows native compilation (`frankenstein.dll`)
- [x] Offline SHA-256d and block assembly verification
- [x] BIP34 height encoding compliance check & fix
- [x] **Real Bitcoin Core regtest block acceptance (validated across heights 3–20)**
- [ ] Next: SegWit witness commitment & transaction selection in templates
- [ ] Next: Durable work journal & tip reorg detection
- [ ] Next: AMD OpenCL backend acceleration
