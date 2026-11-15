# Saucy Public-Puzzle Research Environment

Purpose: provide a portable, reproducible environment for testing two narrow research questions:

1. **Ubuntu 13.10 (Saucy) early-boot variability under QEMU**
   - metadata only
   - no RNG pool contents
   - no raw `/dev/urandom` output
   - no wallet-secret reconstruction

2. **Public solved-puzzle evidence analysis**
   - ingest only already-public solved puzzle data
   - compare structural relationships between known solved entries
   - evaluate historical deterministic-wallet hypotheses at a model level
   - do not derive unknown private keys or unresolved wallet secrets

## Canonical artifact facts

Ubuntu 13.10 desktop AMD64 ISO SHA-256:

`369a1f604df30e097f063829b27c39941a26e5771c53b35aa9ea0e0e0abb3a56`

Squashfs SHA-256:

`58ae7c8ec7c71510fde7899c5cb334829c5e32361d35e42e734edd0a42c172cc`

Confirmed artifact result:

`/var/lib/urandom/random-seed` is absent from the canonical squashfs.
`/var/lib/urandom/` exists and is empty in the release image.

## What this environment measures

The QEMU lane captures only:

- boot ID
- timestamps
- jiffies where available
- CPU number
- IRQ number
- counts of RNG-related kernel events
- initialization milestones
- entropy counters
- `/dev/urandom` read size and timing
- process name responsible for the read

It does **not** store:

- pool words
- entropy payload bytes
- hashes of internal RNG state
- `/dev/urandom` output bytes
- Electrum seeds
- private keys

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/check_environment.py
python scripts/make_boot_plan.py
```

Populate `data/solved_puzzles.csv` only with already-public solved evidence.

Then:

```bash
python scripts/analyze_public_puzzle_evidence.py data/solved_puzzles.csv
```

For QEMU runs, first edit `config/qemu.json` for the local environment, then use:

```bash
python scripts/make_qemu_command.py
```

The script prints a reproducible QEMU command template but does not execute it automatically.

## Decision logic

The Saucy early-boot branch becomes weaker if nominally identical boots show:

- early IRQ-order divergence
- large variation in event counts
- unstable RNG initialization timing
- many distinct event-topology classes

It becomes more interesting if boots show:

- stable IRQ topology
- long common prefixes
- small numbers of repeatable structural variants
- tightly clustered initialization milestones

Neither outcome establishes historical wallet predictability by itself.

## Research separation

Keep the following categories separate in reports:

- **Artifact fact**
- **VM observation**
- **Historical inference**
- **Speculation**
