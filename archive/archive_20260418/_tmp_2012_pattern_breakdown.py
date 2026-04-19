import psycopg2
from psycopg2.extras import RealDictCursor

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)

cur.execute("""
SELECT
  SUM(CASE WHEN COALESCE(description,'') ~* 'BANK FEE|BANK CHARGES|SERVICE CHARGE|OVERDRAFT|NSF FEE|INTEREST' THEN 1 ELSE 0 END) AS fee_rows,
  SUM(CASE WHEN COALESCE(description,'') ~* 'BANK FEE|BANK CHARGES|SERVICE CHARGE|OVERDRAFT|NSF FEE|INTEREST' THEN COALESCE(debit_amount,0) ELSE 0 END) AS fee_amt,
  SUM(CASE WHEN COALESCE(description,'') ~* 'MERCH|MERCHANT' THEN 1 ELSE 0 END) AS merch_rows,
  SUM(CASE WHEN COALESCE(description,'') ~* 'MERCH|MERCHANT' THEN COALESCE(debit_amount,0) ELSE 0 END) AS merch_amt,
  SUM(CASE WHEN COALESCE(description,'') ~* 'CASH WITHDRAWAL|ATM WITHDRAWAL' THEN 1 ELSE 0 END) AS cash_rows,
  SUM(CASE WHEN COALESCE(description,'') ~* 'CASH WITHDRAWAL|ATM WITHDRAWAL' THEN COALESCE(debit_amount,0) ELSE 0 END) AS cash_amt,
  SUM(CASE WHEN COALESCE(description,'') ~* 'CHQ|CHEQUE' OR COALESCE(vendor_extracted,'') ~* 'CHEQUE|CHQ' THEN 1 ELSE 0 END) AS cheque_rows,
  SUM(CASE WHEN COALESCE(description,'') ~* 'CHQ|CHEQUE' OR COALESCE(vendor_extracted,'') ~* 'CHEQUE|CHQ' THEN COALESCE(debit_amount,0) ELSE 0 END) AS cheque_amt
FROM banking_transactions
WHERE EXTRACT(YEAR FROM transaction_date)=2012
  AND COALESCE(debit_amount,0)>0
  AND receipt_id IS NULL
""")
print(dict(cur.fetchone()))

cur.close(); conn.close()
