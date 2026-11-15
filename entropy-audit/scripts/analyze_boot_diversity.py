import json, sys, statistics
from pathlib import Path

def load_jsonl(path):
    rows=[]
    for line in Path(path).read_text().splitlines():
        line=line.strip()
        if line:
            rows.append(json.loads(line))
    return rows

def lcp(a,b):
    n=min(len(a),len(b))
    i=0
    while i<n and a[i]==b[i]:
        i+=1
    return i

if len(sys.argv) < 2:
    print("usage: python scripts/analyze_boot_diversity.py boot_summaries.jsonl")
    raise SystemExit(2)

rows=load_jsonl(sys.argv[1])
print("boots:", len(rows))

seqs=[r.get("irq_sequence",[]) for r in rows]
if len(seqs) >= 2:
    base=seqs[0]
    lcps=[lcp(base,s) for s in seqs[1:]]
    print("IRQ LCP vs boot0:")
    print("  min:", min(lcps))
    print("  median:", statistics.median(lcps))
    print("  max:", max(lcps))

for field in [
    "time_to_rng_init_ms",
    "time_to_first_urandom_read_ms",
    "interrupt_count_before_read",
    "entropy_count_at_read",
    "entropy_total_at_read"
]:
    vals=[r.get(field) for r in rows if isinstance(r.get(field),(int,float))]
    if vals:
        print(field, {
            "min":min(vals),
            "median":statistics.median(vals),
            "max":max(vals)
        })
