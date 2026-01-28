#!/usr/bin/env python3
"""Check account 3648117 for Scotia Bank data."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Check account 3648117 January 2012
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '3648117'
    AND transaction_date >= '2012-01-01'
    AND transaction_date < '2012-02-01'
    ORDER BY transaction_date
    LIMIT 50
""")

rows = cur.fetchall()
print(f"\nAccount 3648117 - January 2012: {len(rows)} transactions")
print("="*120)

for i, row in enumerate(rows, 1):
    date, desc, debit, credit, bal = row
    print(f"{i:3d}. {date} | {desc[:65]:65s} | Dr: ${debit or 0:>9.2f} | Cr: ${credit or 0:>9.2f} | Bal: ${bal or 0:>10.2f}")

# Check first transaction and opening balance
cur.execute("""
    SELECT MIN(transaction_date), COUNT(*), MAX(transaction_date)
    FROM banking_transactions
    WHERE account_number = '3648117'
""")
meta = cur.fetchone()
print(f"\n\nAccount 3648117 Full Range:")
print(f"  Earliest: {meta[0]}")
print(f"  Latest: {meta[2]}")
print(f"  Total Transactions: {meta[1]:,}")

# Check 2012 full year
cur.execute("""
    SELECT 
        TO_CHAR(transaction_date, 'YYYY-MM') as month,
        COUNT(*) as count
    FROM banking_transactions
    WHERE account_number = '3648117'
    AND transaction_date >= '2012-01-01'
    AND transaction_date < '2013-01-01'
    GROUP BY month
    ORDER BY month
""")

print(f"\n\nAccount 3648117 - 2012 Monthly Counts:")
results = cur.fetchall()
for month, count in results:
    print(f"  {month}: {count:4d} rows")

cur.close()
conn.close()
