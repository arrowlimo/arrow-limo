"""Check Scotia Bank January 2012 transactions."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Check Scotia Bank account
cur.execute("""
    SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date),
           ROUND(SUM(COALESCE(debit_amount, 0))::numeric, 2),
           ROUND(SUM(COALESCE(credit_amount, 0))::numeric, 2)
    FROM banking_transactions
    WHERE account_number = '3714081'
    AND transaction_date >= '2012-01-01'
    AND transaction_date < '2012-02-01'
""")

result = cur.fetchone()
print(f"Scotia Bank (3714081) January 2012:")
print(f"  Transactions: {result[0]}")
if result[0] > 0:
    print(f"  Date Range: {result[1]} to {result[2]}")
    print(f"  Total Debits: ${result[3]:,.2f}")
    print(f"  Total Credits: ${result[4]:,.2f}")
else:
    print("  NO DATA FOUND")

# Show first few transactions
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '3714081'
    AND transaction_date >= '2012-01-01'
    AND transaction_date < '2012-02-01'
    ORDER BY transaction_date
    LIMIT 10
""")

print(f"\nFirst 10 transactions:")
for row in cur.fetchall():
    date, desc, debit, credit, balance = row
    print(f"  {date} | {str(desc)[:40]:<40} | D:{debit or 0:>8.2f} C:{credit or 0:>8.2f} B:{balance or 0:>10.2f}")

cur.close()
conn.close()
