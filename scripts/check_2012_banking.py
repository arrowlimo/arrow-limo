import os, psycopg2
conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REMOVED***')
)
cur = conn.cursor()

cur.execute("""
    SELECT COUNT(*) FROM banking_transactions 
    WHERE transaction_date >= '2012-01-01' AND transaction_date < '2013-01-01'
""")
print(f'2012 banking transactions total: {cur.fetchone()[0]:,}')

cur.execute("""
    SELECT DISTINCT account_number FROM banking_transactions 
    WHERE transaction_date >= '2012-01-01' AND transaction_date < '2013-01-01'
    ORDER BY account_number
""")
accts = [r[0] or 'NULL' for r in cur.fetchall()]
print(f'2012 account numbers ({len(accts)}): {", ".join(accts[:10])}')

cur.close()
conn.close()
