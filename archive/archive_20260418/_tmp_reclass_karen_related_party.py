import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
)
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute(
    """
    UPDATE banking_transactions
    SET category = '2550',
        reconciliation_status = 'MANUAL_CLASSIFIED',
        reconciliation_notes = 'Karen Richard related-party reimbursement (internal money movement)',
        updated_at = NOW()
    WHERE debit_amount > 0
      AND receipt_id IS NULL
      AND description ILIKE '%karen richard%'
      AND (
            description ILIKE '%etransfer%'
            OR description ILIKE '%e-transfer%'
            OR description ILIKE '%email transfer%'
          )
    RETURNING transaction_id, debit_amount, description
    """
)
rows = cur.fetchall()
conn.commit()

print(f"RECLASSIFIED_ROWS={len(rows)}")
print(f"RECLASSIFIED_AMOUNT={sum(float(r['debit_amount'] or 0) for r in rows):.2f}")
for r in rows[:10]:
    print(f"{r['transaction_id']}|{r['debit_amount']}|{(r['description'] or '')[:90]}")

cur.close()
conn.close()
