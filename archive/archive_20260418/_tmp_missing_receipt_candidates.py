import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute("""
SELECT EXTRACT(YEAR FROM transaction_date)::int AS yr,
       COUNT(*) AS candidate_rows,
       COALESCE(SUM(debit_amount),0) AS candidate_amt
FROM banking_transactions
WHERE COALESCE(debit_amount,0) > 0
  AND receipt_id IS NULL
  AND COALESCE(description,'') !~* '(transfer|e-?transfer|interac\s*e-?transfer|payment\s+received|deposit|interest|nsf\s*reversal|reversal|refund|cheque\s+deposit|mobile\s+deposit|from\s+account|to\s+account)'
GROUP BY EXTRACT(YEAR FROM transaction_date)
ORDER BY yr DESC
LIMIT 15
""")
print(cur.fetchall())

cur.execute("""
SELECT transaction_date, description, debit_amount, vendor_extracted
FROM banking_transactions
WHERE COALESCE(debit_amount,0) > 0
  AND receipt_id IS NULL
  AND COALESCE(description,'') !~* '(transfer|e-?transfer|interac\s*e-?transfer|payment\s+received|deposit|interest|nsf\s*reversal|reversal|refund|cheque\s+deposit|mobile\s+deposit|from\s+account|to\s+account)'
ORDER BY transaction_date DESC
LIMIT 25
""")
print(cur.fetchall())

cur.close(); conn.close()
