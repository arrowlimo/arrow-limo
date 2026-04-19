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
        reconciliation_notes = 'David Richard family reimbursement (waterfall/cash-box)',
        updated_at = NOW()
    WHERE debit_amount > 0
      AND receipt_id IS NULL
      AND description ILIKE %s
      AND category = 'DRIVER_PAY_REIMBURSEMENT'
    RETURNING transaction_id, debit_amount
    """,
    ("%david richard%",),
)
rows = cur.fetchall()

conn.commit()
cur.close()
conn.close()

amount = sum(float(r["debit_amount"] or 0) for r in rows)
print(f"RECLASSIFIED_ROWS={len(rows)}")
print(f"RECLASSIFIED_AMOUNT={amount:.2f}")
