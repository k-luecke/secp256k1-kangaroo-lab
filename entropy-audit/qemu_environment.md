# QEMU Reproducible Research Environment Specification

## Overview

This document specifies the exact QEMU environment, host constraints, hardware configuration, and execution parameters for evaluating early-boot entropy event topology on the canonical Ubuntu 13.10 (Saucy Salamander) desktop AMD64 ISO.

---

## 1. Host System Details

- **Operating System**: Microsoft Windows 11 Enterprise (Build 22631 / AMD64)
- **Host Architecture**: x86_64 / AMD64
- **PowerShell Version**: PowerShell 5.1 / 7.x
- **Python Runtime**: Python 3.11+ AMD64
- **Scheduling & Determinism Notes**:
  - Windows host scheduling introduces non-deterministic thread preemption jitter unless hardware virtualization (`-accel hax` or `-accel whpx`) and CPU pinning are applied.
  - To test pure software repeatability versus host jitter, Regime A utilizes QEMU's TCG (Tiny Code Generator) single-threaded virtual clock (`-rtc base=utc,clock=vm`), while Regime C permits host scheduling jitter.

---

## 2. QEMU Binary & Version

- **QEMU Binary**: `C:\Program Files\GNS3\qemu-3.1.0\qemu-system-x86_64.exe`
- **Reported Version**: `QEMU emulator version 2.11.0 (v2.11.0-11693-g21057c841e-dirty)`
- **Target Architecture**: `x86_64`

---

## 3. Machine Hardware Configuration (Frozen Baseline - Regime A)

| Parameter | Configuration Value | Rationale |
| :--- | :--- | :--- |
| **Machine Type** | `-machine pc` | Standard PC (i440FX + PIIX, 1996) legacy chipset |
| **CPU Model** | `-cpu qemu64` | Standard synthetic QEMU 64-bit CPU model |
| **vCPU Count** | `-smp 1` | Single vCPU eliminates inter-core race conditions in early boot |
| **RAM** | `-m 2048` | 2048 MB memory allocation |
| **Storage Controller** | IDE / PIIX3 | Native IDE controller for CD-ROM media |
| **Media / Boot Device**| `-cdrom ubuntu-13.10-desktop-amd64.iso -boot d` | Canonical Ubuntu 13.10 Live ISO |
| **Network Interface** | `-nic none` | Network completely disabled to prevent external packet IRQs |
| **RTC Clock** | `-rtc base=2013-10-17T12:00:00,clock=vm` | Fixed historical release date and virtualized monotonic clock |
| **Serial / Console** | `-serial file:traces_metadata/boot_serial.log` | Directed trace output to capture instrumentation |
| **Display** | `-nographic -vga none` | Headless execution removes graphical timing interrupts |
| **Reboot Behavior** | `-no-reboot` | Halts VM upon test completion or shutdown |

---

## 4. Canonical Artifact Hashes

- **Ubuntu 13.10 Desktop AMD64 ISO**:
  - File: `ubuntu-13.10-desktop-amd64.iso`
  - SHA-256: `369a1f604df30e097f063829b27c39941a26e5771c53b35aa9ea0e0e0abb3a56`
- **Squashfs Root Filesystem**:
  - File: `casper/filesystem.squashfs`
  - SHA-256: `58ae7c8ec7c71510fde7899c5cb334829c5e32361d35e42e734edd0a42c172cc`
  - Verified Content: `/var/lib/urandom/` is empty; `/var/lib/urandom/random-seed` is **absent**.

---

## 5. Execution Regimes & Launch Commands

### Regime A: Maximum Repeatability (100 Boots)
```bash
qemu-system-x86_64 \
  -machine pc \
  -cpu qemu64 \
  -m 2048 \
  -smp 1 \
  -cdrom ubuntu-13.10-desktop-amd64.iso \
  -boot d \
  -nic none \
  -rtc base=2013-10-17T12:00:00,clock=vm \
  -nographic \
  -vga none \
  -serial file:traces_metadata/regime_a_boot_{ID}.log \
  -append "console=ttyS0,115200 quiet nosplash rng_trace=metadata" \
  -no-reboot
```

### Regime B: Single-Variable Perturbations
1. **RTC Offset +1s**: `-rtc base=2013-10-17T12:00:01,clock=vm`
2. **SMP 2 vCPUs**: `-smp 2`
3. **NIC Enabled**: `-netdev user,id=n0 -device e1000,netdev=n0,mac=52:54:00:12:34:56`
4. **USB Controller Added**: `-device usb-ehci,id=ehci`
5. **Storage Timing Variant**: IDE vs VirtIO SCSI (`-drive file=live.iso,if=virtio,media=cdrom`)

### Regime C: Ordinary VM Host Jitter (100 Boots)
```bash
qemu-system-x86_64 \
  -machine pc \
  -cpu qemu64 \
  -m 2048 \
  -smp 1 \
  -cdrom ubuntu-13.10-desktop-amd64.iso \
  -boot d \
  -nic none \
  -rtc base=localtime,clock=host \
  -nographic \
  -vga none \
  -serial file:traces_metadata/regime_c_boot_{ID}.log \
  -append "console=ttyS0,115200 quiet nosplash rng_trace=metadata" \
  -no-reboot
```
