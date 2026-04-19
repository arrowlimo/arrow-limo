import csv
from collections import defaultdict
from pathlib import Path

IN_CSV = Path(r"l:\limo\data\intake\etransfer_remaining_fuzzy_review.csv")
OUT_MANUAL = Path(r"l:\limo\data\intake\manual_review_grouped_by_name.csv")

if not IN_CSV.exists():
    raise FileNotFoundError(IN_CSV)

# Group all manual-review rows by candidate_name.
groups = defaultdict(lambda: {"rows": [], "sum_amount": 0.0, "best_emp": "", "best_conf": 0.0})

with IN_CSV.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    for r in reader:
        if (r.get("recommended_lane") or "").strip() != "MANUAL_REVIEW":
            continue

        cand = (r.get("candidate_name") or "").strip()
        if not cand:
            continue

        amt = float((r.get("debit_amount") or "0").strip() or 0)
        best_emp = (r.get("best_employee_name") or "").strip()
        best_conf = float((r.get("best_confidence") or "0").strip() or 0)

        g = groups[cand]
        g["rows"].append(r)
        g["sum_amount"] += amt
        if best_conf > g["best_conf"]:
            g["best_conf"] = best_conf
            g["best_emp"] = best_emp

# Sort by count descending, then amount.
sorted_groups = sorted(
    groups.items(),
    key=lambda x: (len(x[1]["rows"]), x[1]["sum_amount"]),
    reverse=True,
)

print(f"MANUAL_REVIEW_GROUPS={len(sorted_groups)}")
print("TOP_GROUPS_BY_COUNT")
for cand, g in sorted_groups[:100]:
    print(
        f"{cand}|{len(g['rows'])}|{g['sum_amount']:,.2f}|{g['best_emp']}|{g['best_conf']:.4f}"
    )

# Write full detail for inspection.
with OUT_MANUAL.open("w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["candidate_name", "count", "total_amount", "best_employee", "best_confidence", "group_index"])
    for idx, (cand, g) in enumerate(sorted_groups):
        writer.writerow([cand, len(g["rows"]), f"{g['sum_amount']:.2f}", g["best_emp"], f"{g['best_conf']:.4f}", idx])

print(f"GROUPED_CSV={OUT_MANUAL}")

# Show largest groups for quick approval targeting.
print("TOP_10_GROUPS_SUMMARY")
for idx, (cand, g) in enumerate(sorted_groups[:10]):
    print(f"GROUP_{idx}|{cand}|rows={len(g['rows'])}|amount={g['sum_amount']:.2f}|emp={g['best_emp']}")
