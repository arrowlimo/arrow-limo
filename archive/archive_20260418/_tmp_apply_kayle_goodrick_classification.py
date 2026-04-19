import psycopg2
from psycopg2.extras import RealDictCursor

DB_PARAMS = {
    "host": "localhost",
    "port": 5432,
    "database": "almsdata",
    "user": "postgres",
    "password": "ArrowLimousine",
}

conn = psycopg2.connect(**DB_PARAMS)
cur = conn.cursor(cursor_factory=RealDictCursor)

sql = """
UPDATE banking_transactions
SET category = %s,
    reconciliation_status = %s,
    reconciliation_notes = %s,
    updated_at = NOW()
WHERE description ILIKE %s
  AND debit_amount > 0
  AND receipt_id IS NULL
RETURNING transaction_id, debit_amount;
"""

cur.execute(
    sql,
    (
        "VENDOR_SERVICE",
        "MANUAL_CLASSIFIED",
        "Kayle Goodrick - general contractor, vehicle repair",
        "%kayle goodrick%",
    ),
)
rows = cur.fetchall()
count = len(rows)
amount = sum(float(r["debit_amount"] or 0) for r in rows)

conn.commit()
cur.close()
conn.close()

print(f"UPDATED_ROWS={count}")
print(f"UPDATED_AMOUNT={amount:.2f}")
