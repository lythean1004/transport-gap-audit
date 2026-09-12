from pathlib import Path
import shutil

SRC = Path("src/verify/stop_gate.py")
lines = SRC.read_text(encoding="utf-8").splitlines()

print("---- promote_stop (637~771) ----")
for i in range(636, min(771, len(lines))):
    print(f"{i+1:5d}: {lines[i]}")

BAK = Path("scratch/stop_registry.pre_promote.bak")
BAK.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2("evidence/stop_registry.csv", BAK)
print("\nbackup:", BAK, "exists:", BAK.exists(), "size:", BAK.stat().st_size)