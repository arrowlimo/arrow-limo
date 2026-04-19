import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

print('UNRESOLVED_ETRANSFER_REMAINING')
cur.execute(
    """
    SELECT
      COUNT(1),
      COALESCE(SUM(debit_amount),0)
    FROM banking_transactions
    WHERE debit_amount > 0
      AND receipt_id IS NULL
      AND reconciled_receipt_id IS NULL
      AND reconciled_payment_id IS NULL
      AND reconciled_charter_id IS NULL
      AND reconciliation_status IS DISTINCT FROM 'CASH_BOX_REVIEW'
      AND (description ILIKE '%e-transfer%' OR description ILIKE '%etransfer%' OR description ILIKE '%email transfer%')
      AND reconciliation_status IS DISTINCT FROM 'DRIVER_PAY_FUZZY'
    """
)
print(cur.fetchone())

print('ETRANSFER_STATUS_BREAKDOWN')
cur.execute(
    """
    SELECT COALESCE(reconciliation_status, 'NULL') AS status,
           COUNT(1),
           COALESCE(SUM(debit_amount),0)
    FROM banking_transactions
    WHERE debit_amount > 0
      AND receipt_id IS NULL
      AND reconciled_receipt_id IS NULL
      AND reconciled_payment_id IS NULL
      AND reconciled_charter_id IS NULL
      AND (description ILIKE '%e-transfer%' OR description ILIKE '%etransfer%' OR description ILIKE '%email transfer%')
    GROUP BY COALESCE(reconciliation_status, 'NULL')
    ORDER BY COUNT(1) DESC
    """
)
for row in cur.fetchall():
    print('|'.join(str(x) for x in row))

cur.close()
conn.close()
