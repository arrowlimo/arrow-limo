import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

print('DRIVER_PAY_FUZZY_SUMMARY')
cur.execute(
    """
    SELECT COUNT(1), COALESCE(SUM(debit_amount),0)
    FROM banking_transactions
    WHERE reconciliation_status='DRIVER_PAY_FUZZY'
    """
)
print(cur.fetchone())

print('CATEGORY_DRIVER_PAY_REIMBURSEMENT_SUMMARY')
cur.execute(
    """
    SELECT COUNT(1), COALESCE(SUM(debit_amount),0)
    FROM banking_transactions
    WHERE category='DRIVER_PAY_REIMBURSEMENT'
    """
)
print(cur.fetchone())

print('TOP_FUZZY_EMPLOYEES')
cur.execute(
    """
    SELECT
      substring(reconciliation_notes from 'employee=(.*) \(id=') as employee_name,
      COUNT(1),
      COALESCE(SUM(debit_amount),0)
    FROM banking_transactions
    WHERE reconciliation_status='DRIVER_PAY_FUZZY'
      AND reconciliation_notes ILIKE '%etransfer_fuzzy_driver_match%'
    GROUP BY 1
    ORDER BY COUNT(1) DESC, COALESCE(SUM(debit_amount),0) DESC
    LIMIT 25
    """
)
for row in cur.fetchall():
    print('|'.join(str(x) for x in row))

print('JEANNIE_VARIANTS_CHECK')
cur.execute(
    """
    SELECT transaction_id, transaction_date, debit_amount, description, reconciliation_status
    FROM banking_transactions
    WHERE reconciliation_status='DRIVER_PAY_FUZZY'
      AND (
         description ILIKE '%JEANNIE%'
         OR description ILIKE '%JENNEE%'
         OR description ILIKE '%JEANY%'
         OR description ILIKE '%SHILLINGTON%'
      )
    ORDER BY transaction_date DESC, transaction_id DESC
    LIMIT 50
    """
)
for row in cur.fetchall():
    print('|'.join(str(x) for x in row))

cur.close()
conn.close()
