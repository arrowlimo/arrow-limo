import csv
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

p = Path(r"L:\limo\data\intake\cash_box_queue_decision_sheet.csv")
rows = list(csv.DictReader(open(p, "r", encoding="utf-8")))

print(f"CASHBOX_DECISION_ROWS={len(rows)}")
print("SAMPLES")
for r in rows[:20]:
    print(
        f"{r['transaction_id']}|{r['transaction_date']}|{r['debit_amount']}|"
        f"{r['recommended_action']}|{r['suggested_gl']}|{r['rule']}|"
        f"{r['vendor_extracted'][:25]}|{r['description'][:70]}"
    )

DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "almsdata",
    "user": "postgres",
    "password": "ArrowLimousine",
}
conn = psycopg2.connect(**DB)
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute("SELECT COUNT(*) AS c, COALESCE(SUM(debit_amount),0) AS amt FROM banking_transactions WHERE reconciliation_status='CASH_BOX_REVIEW'")
r = cur.fetchone()
print("TAGGED_STATUS")
print(f"cash_box_review_rows={r['c']}")
print(f"cash_box_review_amount={r['amt']}")
cur.close(); conn.close()
