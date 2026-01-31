import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance 
    FROM banking_transactions 
    WHERE account_number = '0228362' 
    AND transaction_date BETWEEN '2014-11-01' AND '2014-12-31' 
    ORDER BY transaction_date
""")

rows = cur.fetchall()
print(f"\nNov-Dec 2014: {len(rows)} transactions\n")

for r in rows:
    date, desc, debit, credit, balance = r
    desc_short = (desc or '')[:50]
    print(f"{date} {desc_short:50} D:{debit or 0:>10.2f} C:{credit or 0:>10.2f} Bal:{balance if balance is not None else 'NULL':>10}")

cur.close()
conn.close()
