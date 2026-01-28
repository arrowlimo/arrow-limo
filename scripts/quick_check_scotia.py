import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("""
    SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date), 
           SUM(COALESCE(debit_amount,0)), SUM(COALESCE(credit_amount,0))
    FROM banking_transactions 
    WHERE account_number='903990106011'
""")
r = cur.fetchone()
print(f'Account 903990106011 (Scotia Bank):')
print(f'  Total Rows: {r[0]:,}')
print(f'  Date Range: {r[1]} to {r[2]}')
print(f'  Total Debits: ${r[3]:,.2f}')
print(f'  Total Credits: ${r[4]:,.2f}')

cur.execute("""
    SELECT COUNT(*) FROM banking_transactions 
    WHERE account_number='903990106011' 
    AND transaction_date>='2012-01-01' AND transaction_date<'2013-01-01'
""")
print(f'  2012 Rows: {cur.fetchone()[0]:,}')

cur.close()
conn.close()
