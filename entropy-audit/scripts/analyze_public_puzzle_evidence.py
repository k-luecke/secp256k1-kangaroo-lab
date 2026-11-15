import sys
import pandas as pd
from pathlib import Path

if len(sys.argv) < 2:
    print("usage: python scripts/analyze_public_puzzle_evidence.py data/solved_puzzles.csv")
    raise SystemExit(2)

path = Path(sys.argv[1])
df = pd.read_csv(path, comment="#")

if df.empty:
    print("No solved-puzzle rows loaded.")
    raise SystemExit(0)

required = {"puzzle_id","address","source"}
missing = required - set(df.columns)
if missing:
    raise SystemExit(f"missing required columns: {sorted(missing)}")

print("Rows:", len(df))
print("Unique puzzles:", df["puzzle_id"].nunique())
print("Unique addresses:", df["address"].nunique())

# Structural/public-evidence-only checks.
print("\nDuplicate addresses:")
dups = df[df.duplicated("address", keep=False)].sort_values("address")
print(dups[["puzzle_id","address","source"]].to_string(index=False) if len(dups) else "none")

if "private_key_hex" in df.columns:
    public = df["private_key_hex"].fillna("").astype(str)
    lens = public[public.str.len() > 0].str.len().value_counts().sort_index()
    print("\nKnown-solved private-key hex lengths:")
    print(lens.to_string() if len(lens) else "none")

print("\nThis script intentionally does not derive unresolved private keys.")
