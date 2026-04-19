import csv
from pathlib import Path

safe = Path(r"L:\limo\data\intake\unlinked_debits_auto_safe_queue.csv")
review = Path(r"L:\limo\data\intake\unlinked_debits_manual_review_queue.csv")

for name, p in [("AUTO_SAFE", safe), ("MANUAL_REVIEW", review)]:
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    print(f"{name}_COUNT={len(rows)}")
    print(f"{name}_SAMPLES")
    for r in rows[:15]:
        print(
            f"{r['group']}|{r['transaction_id']}|{r['transaction_date']}|"
            f"{r['debit_amount']}|{(r.get('vendor_extracted') or '')[:30]}|"
            f"{(r.get('description') or '')[:70]}"
        )
    print()
