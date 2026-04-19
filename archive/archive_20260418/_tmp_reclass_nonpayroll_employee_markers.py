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

# Convert manually classified EMPLOYEE_PAY e-transfer rows to non-payroll related-party bucket.
cur.execute(
    """
    UPDATE banking_transactions
    SET category = '2550',
        reconciliation_notes = COALESCE(reconciliation_notes || E'\n', '') ||
            '[POLICY] Non-payroll reimbursement marker; payroll/source deductions come only from driver pay management (PD7/T4).',
        updated_at = NOW()
    WHERE debit_amount > 0
      AND receipt_id IS NULL
      AND reconciliation_status = 'MANUAL_CLASSIFIED'
      AND category = 'EMPLOYEE_PAY'
      AND (
            description ILIKE '%etransfer%'
            OR description ILIKE '%e-transfer%'
            OR description ILIKE '%email transfer%'
          )
    RETURNING transaction_id, debit_amount
    """
)
rows = cur.fetchall()
conn.commit()

print(f"RECLASSIFIED_EMPLOYEE_PAY_ROWS={len(rows)}")
print(f"RECLASSIFIED_EMPLOYEE_PAY_AMOUNT={sum(float(r['debit_amount'] or 0) for r in rows):.2f}")

cur.close()
conn.close()
