import csv
from collections import defaultdict
from pathlib import Path

IN_CSV = Path(r"l:\limo\data\intake\etransfer_remaining_fuzzy_review.csv")
OUT_CSV = Path(r"l:\limo\data\intake\etransfer_alias_suggestions.csv")

if not IN_CSV.exists():
    raise FileNotFoundError(IN_CSV)

agg = defaultdict(lambda: {"count": 0, "amount": 0.0, "best_emp": "", "best_conf": 0.0, "second_conf": 0.0})

with IN_CSV.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    for r in reader:
        cand = (r.get("candidate_name") or "").strip()
        if not cand:
            continue
        amt = float((r.get("debit_amount") or "0").strip() or 0)
        best_emp = (r.get("best_employee_name") or "").strip()
        best = float((r.get("best_confidence") or "0").strip() or 0)
        second = float((r.get("second_confidence") or "0").strip() or 0)

        d = agg[cand]
        d["count"] += 1
        d["amount"] += amt
        if best > d["best_conf"]:
            d["best_conf"] = best
            d["second_conf"] = second
            d["best_emp"] = best_emp

rows = []
for cand, d in agg.items():
    rows.append(
        {
            "candidate_name": cand,
            "count": d["count"],
            "amount": f"{d['amount']:.2f}",
            "best_employee_name": d["best_emp"],
            "peak_best_confidence": f"{d['best_conf']:.4f}",
            "peak_second_confidence": f"{d['second_conf']:.4f}",
            "suggest_add_alias": "yes" if d["count"] >= 2 and d["best_conf"] >= 0.75 else "review",
        }
    )

rows.sort(key=lambda x: (int(x["count"]), float(x["amount"])), reverse=True)

with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "candidate_name",
            "count",
            "amount",
            "best_employee_name",
            "peak_best_confidence",
            "peak_second_confidence",
            "suggest_add_alias",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)

print(f"ALIAS_CANDIDATE_NAMES={len(rows)}")
print(f"ALIAS_SUGGESTIONS_CSV={OUT_CSV}")
print("TOP_ALIAS_SUGGESTIONS")
for r in rows[:40]:
    print(
        f"{r['candidate_name']}|{r['count']}|{r['amount']}|{r['best_employee_name']}|"
        f"{r['peak_best_confidence']}|{r['suggest_add_alias']}"
    )
