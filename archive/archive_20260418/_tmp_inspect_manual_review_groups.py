import csv
from collections import defaultdict
from pathlib import Path

IN_CSV = Path(r"l:\limo\data\intake\etransfer_remaining_fuzzy_review.csv")

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

# Show top 15 groups in detail
print("=" * 100)
print("TOP_15_MANUAL_REVIEW_GROUPS_FOR_APPROVAL")
print("=" * 100)

for idx, (cand, g) in enumerate(sorted_groups[:15]):
    print(f"\nGROUP_{idx}: {cand}")
    print(f"  COUNT={len(g['rows'])} | TOTAL=${g['sum_amount']:,.2f} | BEST_MATCH={g['best_emp']} (conf={g['best_conf']:.4f})")
    print(f"  SAMPLE_ROW_DETAILS:")

    # Show first 3 rows from this group
    for row_idx, row in enumerate(g["rows"][:3]):
        trans_date = (row.get("transaction_date") or "").strip()
        debit_amt = (row.get("debit_amount") or "0").strip()
        desc = (row.get("description") or "").strip()[:80]
        best_emp_name = (row.get("best_employee_name") or "").strip()
        best_conf = (row.get("best_confidence") or "0").strip()

        print(
            f"    [{row_idx+1}] {trans_date} | ${debit_amt} | BEST={best_emp_name} ({best_conf}) | DESC: {desc}"
        )

    if len(g["rows"]) > 3:
        print(f"    ... and {len(g['rows']) - 3} more rows")

print("\n" + "=" * 100)
print("APPROVAL_PROMPT")
print("=" * 100)
print("Review GROUP_0 first (MIKE WOODROW, 359 rows, $207,577.76).")
print("Should we approve this group to DRIVER_PAY_REIMBURSEMENT? (yes/no/review)")
print("Then GROUP_1, etc.")
print("Reply with approval decisions separated by commas: 'GROUP_0=yes,GROUP_1=no,GROUP_2=yes'")
