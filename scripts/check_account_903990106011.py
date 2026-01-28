"""Check account 903990106011 sample transactions."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    ORDER BY transaction_date
    LIMIT 15
""")

print("Account 903990106011 - First 15 transactions:")
print(f"{'Date':<12} | {'Description':<45} | {'Debit':>9} | {'Credit':>9} | {'Balance':>10}")
print("-" * 100)
for row in cur.fetchall():
    date, desc, debit, credit, balance = row
    print(f"{date} | {str(desc)[:45]:<45} | {debit or 0:9.2f} | {credit or 0:9.2f} | {balance or 0:10.2f}")

cur.close()
conn.close()
