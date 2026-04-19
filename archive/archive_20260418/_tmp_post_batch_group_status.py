import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
)
cur = conn.cursor()

print("TRANSFER_REVIEW_SUMMARY")
cur.execute(
    """
    SELECT COUNT(1), COALESCE(SUM(debit_amount),0)
    FROM banking_transactions
    WHERE reconciliation_status='TRANSFER_REVIEW'
    """
)
print(cur.fetchone())

print("CASH_BOX_REVIEW_SUMMARY")
cur.execute(
    """
    SELECT COUNT(1), COALESCE(SUM(debit_amount),0)
    FROM banking_transactions
    WHERE reconciliation_status='CASH_BOX_REVIEW'
    """
)
print(cur.fetchone())

print("UNLINKED_DEBIT_POOL")
cur.execute(
    """
    SELECT COUNT(1), COALESCE(SUM(debit_amount),0)
    FROM banking_transactions bt
    WHERE bt.debit_amount > 0
      AND bt.receipt_id IS NULL
      AND bt.reconciled_receipt_id IS NULL
      AND bt.reconciled_payment_id IS NULL
      AND bt.reconciled_charter_id IS NULL
    """
)
print(cur.fetchone())

cur.close()
conn.close()
