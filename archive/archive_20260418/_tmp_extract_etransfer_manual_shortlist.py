import csv
from pathlib import Path

IN_CSV = Path(r"l:\limo\data\intake\etransfer_remaining_fuzzy_review.csv")
OUT_CSV = Path(r"l:\limo\data\intake\etransfer_remaining_fuzzy_shortlist.csv")

if not IN_CSV.exists():
    raise FileNotFoundError(IN_CSV)

rows = []
with IN_CSV.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    for r in reader:
        best = float((r.get("best_confidence") or "0").strip() or 0)
        gap = float((r.get("confidence_gap") or "0").strip() or 0)
        status = (r.get("reconciliation_status") or "").strip()

        # Conservative shortlist: likely employee name but uncertain enough to require click-through review.
        if best >= 0.72 and gap >= 0.015:
            rr = dict(r)
            rr["shortlist_reason"] = "highish_confidence_name_match"
            rr["status_hint"] = "non_payroll_reimbursement_review"
            rows.append(rr)

rows.sort(
    key=lambda x: (
        float(x.get("best_confidence") or 0),
        float(x.get("confidence_gap") or 0),
        float(x.get("debit_amount") or 0),
    ),
    reverse=True,
)

with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
    fieldnames = list(rows[0].keys()) if rows else [
        "transaction_id", "transaction_date", "debit_amount", "reconciliation_status",
        "description", "candidate_name", "best_employee_name", "best_confidence",
        "second_confidence", "confidence_gap", "shortlist_reason", "status_hint"
    ]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"SHORTLIST_ROWS={len(rows)}")
print(f"SHORTLIST_CSV={OUT_CSV}")
print("TOP_SHORTLIST")
for r in rows[:30]:
    print(
        f"{r['transaction_id']}|{r['debit_amount']}|{r['candidate_name']}|{r['best_employee_name']}|"
        f"{r['best_confidence']}|{r['confidence_gap']}|{r['reconciliation_status']}"
    )
