# Linux 3.11 RNG Metadata Instrumentation Guide

## Purpose & Scope
This patch instruments `drivers/char/random.c` in Linux kernel v3.11 (the kernel shipped with Ubuntu 13.10 Saucy Salamander) specifically to capture **event-structure metadata** during early boot.

## Safety & Non-Exposure Guarantees
In strict accordance with research safety constraints:
1. **No Pool Words**: The internal entropy store arrays (`r->pool`, `fast_pool->pool`) are never read, copied, or serialized.
2. **No Payload Bytes**: Buffers passed to `add_device_randomness()` or `add_interrupt_randomness()` are never logged.
3. **No Key or Seed Material**: Output bytes returned by `urandom_read()` to userspace are never logged.
4. **Metadata Only**: The log contains exclusively:
   - Event names (`add_interrupt_randomness`, `fast_pool_promotion`, `xfer_secondary_pool`, `urandom_read`, etc.)
   - Sequence counts and monotonic timestamps (`ktime_get()`, `jiffies`, `get_cycles()`)
   - Hardware identifiers: CPU ID, IRQ number, Instruction Pointer (`_RET_IP_`)
   - Entropy accounting levels (`entropy_count`, `entropy_total`)
   - Calling process context (`current->comm`, `current->pid`, requested byte size)

## Extraction / Capture Channel
The patch formats metadata events as structured JSON strings prefixed with `[RNG_META]`. When running QEMU with `-serial file:traces_metadata/boot_serial.log console=ttyS0`, the guest kernel writes these lines directly to the virtual serial port, enabling host-side ingestion into JSONL trace files without modifying userland storage.
