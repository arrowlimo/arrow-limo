"""Check January 2012 banking transactions."""
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
    WHERE account_number = '0228362'
    AND transaction_date >= '2012-01-01'
    AND transaction_date < '2012-02-01'
    ORDER BY transaction_date
    LIMIT 30
""")

print("January 2012 Banking Transactions (Account 0228362):")
print(f"{'Date':<12} | {'Description':<35} | {'Debit':>10} | {'Credit':>10} | {'Balance':>10}")
print("-" * 90)

for row in cur.fetchall():
    date, desc, debit, credit, balance = row
    print(f"{date} | {str(desc)[:35]:<35} | {debit or 0:>10.2f} | {credit or 0:>10.2f} | {balance or 0:>10.2f}")

cur.close()
conn.close()
