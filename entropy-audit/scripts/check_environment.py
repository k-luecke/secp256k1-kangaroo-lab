from pathlib import Path
import shutil, json, hashlib

cfg = json.loads(Path("config/qemu.json").read_text())

print("Environment check")
print("=================")
for exe in [cfg["qemu_binary"], "python3"]:
    print(f"{exe}: {shutil.which(exe) or 'NOT FOUND'}")

iso = Path(cfg["iso_path"])
if iso.exists():
    h = hashlib.sha256()
    with iso.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    print("ISO SHA-256:", h.hexdigest())
    print("Expected:    369a1f604df30e097f063829b27c39941a26e5771c53b35aa9ea0e0e0abb3a56")
else:
    print("ISO not found at configured path:", iso)
