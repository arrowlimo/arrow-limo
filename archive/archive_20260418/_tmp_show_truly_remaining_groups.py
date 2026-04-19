import csv
from collections import defaultdict
from pathlib import Path

IN_CSV = Path(r"l:\limo\data\intake\etransfer_remaining_fuzzy_review.csv")

if not IN_CSV.exists():
    raise FileNotFoundError(IN_CSV)

# Already classified candidates
CLASSIFIED = {
    "MIKE WOODROW",
    "VANESSA THOMAS",
    "BRITT",
    "MUNDY DIANNE",
    "SAM RONEY",
    "DAVE MUNDY",
    "FEE",
    "KEVIN SPROULE",
    "PAT PERRIER",
    "VALIN HEATH",
    "GEOFF TAGG",
    "TABATHA WOW WIND",
    "SHEILA FRIESEN",
    "KARMA SCHOPP",
    "LINDA",
    "ONE TIME CONTACT",
    "RD REGIONAL AIRPORT",
    "DIRECT DIGITAL",
    "DARRYL TABOO SHOWS",
    "SERENA BOOK KEEPER",
}

# Group remaining UNCLASSIFIED rows by candidate_name
groups = defaultdict(lambda: {"rows": [], "sum_amount": 0.0, "best_emp": "", "best_conf": 0.0})

with IN_CSV.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    for r in reader:
        if (r.get("recommended_lane") or "").strip() != "MANUAL_REVIEW":
            continue

        cand = (r.get("candidate_name") or "").strip()
        if not cand or cand in CLASSIFIED:
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

# Sort by count descending
sorted_groups = sorted(
    groups.items(),
    key=lambda x: (len(x[1]["rows"]), x[1]["sum_amount"]),
    reverse=True,
)

print(f"\nREMAINING_UNCLASSIFIED_GROUPS: {len(sorted_groups)}")
print("=" * 100)

for idx, (cand, g) in enumerate(sorted_groups):
    print(f"\nUNCLASSIFIED_{idx}: {cand}")
    print(f"  COUNT={len(g['rows'])} | TOTAL=${g['sum_amount']:,.2f} | BEST_MATCH={g['best_emp']} (conf={g['best_conf']:.4f})")
    for row_idx, row in enumerate(g["rows"][:2]):
        trans_date = (row.get("transaction_date") or "").strip()
        debit_amt = (row.get("debit_amount") or "0").strip()
        desc = (row.get("description") or "").strip()[:60]
        print(f"    [{row_idx+1}] {trans_date} | ${debit_amt} | {desc}")
    if len(g["rows"]) > 2:
        print(f"    ... and {len(g['rows']) - 2} more rows")

print("\n" + "=" * 100)
total_remaining = sum(len(g['rows']) for g in groups.values())
total_amt = sum(g['sum_amount'] for g in groups.values())
print(f"TOTAL_UNCLASSIFIED: {total_remaining} rows, ${total_amt:,.2f}")
print("=" * 100)
