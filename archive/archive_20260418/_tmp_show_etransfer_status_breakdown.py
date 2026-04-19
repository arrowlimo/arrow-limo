import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict

DB_PARAMS = {
    "host": "localhost",
    "port": 5432,
    "database": "almsdata",
    "user": "postgres",
    "password": "ArrowLimousine",
}

conn = psycopg2.connect(**DB_PARAMS)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Get all outbound e-transfer rows that are still NOT linked to receipts
sql = """
SELECT 
    transaction_id,
    transaction_date,
    debit_amount,
    description,
    category,
    reconciliation_status,
    reconciliation_notes
FROM banking_transactions
WHERE debit_amount > 0
  AND (description ILIKE '%etransfer%' OR description ILIKE '%e-transfer%' OR description ILIKE '%email transfer%')
  AND receipt_id IS NULL
  AND reconciliation_status NOT IN ('SCHEDULED_EXPENSE', 'PAYROLL', 'LEASE', 'BANKING_TRANSFER', 'INTERNAL')
ORDER BY category, transaction_date;
"""

cur.execute(sql)
rows = cur.fetchall()

# Group by category and reconciliation_status
status_groups = defaultdict(lambda: {"rows": [], "amount": 0.0})

for r in rows:
    key = f"{r['category']} | {r['reconciliation_status']}"
    status_groups[key]["rows"].append(r)
    status_groups[key]["amount"] += float(r["debit_amount"] or 0)

cur.close()
conn.close()

# Sort by count descending
sorted_groups = sorted(
    status_groups.items(),
    key=lambda x: len(x[1]["rows"]),
    reverse=True,
)

print("=" * 100)
print("UNMATCHED_ETRANSFER_POOL_BY_STATUS")
print("=" * 100)

for idx, (key, g) in enumerate(sorted_groups[:20]):
    print(f"\n[{idx}] {key}")
    print(f"    COUNT={len(g['rows'])} | TOTAL=${g['amount']:,.2f}")
    for row_idx, r in enumerate(g["rows"][:2]):
        trans_date = r["transaction_date"]
        amt = r["debit_amount"]
        desc = (r["description"] or "")[:70]
        print(f"      [{row_idx+1}] {trans_date} | ${amt} | {desc}")
    if len(g["rows"]) > 2:
        print(f"      ... and {len(g['rows']) - 2} more")

print("\n" + "=" * 100)
print(f"TOTAL_UNMATCHED_ETRANSFERS: {len(rows)} rows, ${sum(float(r['debit_amount'] or 0) for r in rows):,.2f}")
print("=" * 100)
