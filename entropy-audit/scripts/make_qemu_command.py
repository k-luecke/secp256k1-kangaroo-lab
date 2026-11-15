from pathlib import Path
import json, shlex

cfg = json.loads(Path("config/qemu.json").read_text())

cmd = [
    cfg["qemu_binary"],
    "-machine", cfg["machine"],
    "-cpu", cfg["cpu"],
    "-m", str(cfg["memory_mb"]),
    "-smp", str(cfg["smp"]),
    "-cdrom", cfg["iso_path"],
    "-boot", cfg["boot"],
    "-rtc", cfg["rtc"],
]

if cfg.get("network") == "none":
    cmd += ["-nic", "none"]
else:
    cmd += ["-netdev", f"user,id=n0", "-device", f'{cfg["nic_model"]},netdev=n0,mac={cfg["mac"]}']

cmd += cfg.get("extra_args", [])

print(" ".join(shlex.quote(x) for x in cmd))
