# Handoff to another environment

You are continuing a historical/public-puzzle research project.

The immediate task is **not** to reconstruct wallet secrets.

Run two independent lanes:

## Lane 1 — Saucy QEMU boot metadata

Use the canonical Ubuntu 13.10 desktop AMD64 ISO.

Known ISO SHA-256:
`369a1f604df30e097f063829b27c39941a26e5771c53b35aa9ea0e0e0abb3a56`

Known squashfs SHA-256:
`58ae7c8ec7c71510fde7899c5cb334829c5e32361d35e42e734edd0a42c172cc`

Confirmed:
`/var/lib/urandom/random-seed` is absent.

Measure only boot-event metadata:
- IRQ ordering/counts
- RNG initialization timing
- entropy counters
- RNG-related call counts
- `/dev/urandom` read timing/size

Do not record internal pool contents or returned random bytes.

Goal:
Determine whether early-boot event topology is structurally stable or chaotic across repeated nominally identical QEMU boots.

## Lane 2 — Public solved-puzzle evidence

Use only already-public solved puzzle records.

Goal:
Characterize structural evidence that might distinguish competing historical creation recipes.

Allowed:
- compare solved records
- identify duplicated collectors
- sequence solved puzzle IDs
- test metadata-level deterministic-wallet hypotheses
- quantify how public solved evidence constrains a model family

Do not:
- derive unknown private keys
- search unresolved keyspace
- reconstruct raw wallet RNG state

## Scientific output

Keep facts, VM observations, historical inference, and speculation separate.

A good result may simply be:
- "controlled VM boot structure is highly variable", or
- "controlled VM boot structure is surprisingly repeatable."

Neither result alone proves anything about historical wallet predictability.
