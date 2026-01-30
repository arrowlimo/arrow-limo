#!/usr/bin/env python3
"""Check for 2012 banking data in banking_transactions table."""
import os
import psycopg2

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REDACTED***'),
)
cur = conn.cursor()

print("=== Checking banking_transactions for 2012 ===")
cur.execute("""
    SELECT 
        COUNT(*) as count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        SUM(CASE WHEN debit_amount IS NOT NULL THEN debit_amount ELSE 0 END) as total_debits,
        SUM(CASE WHEN credit_amount IS NOT NULL THEN credit_amount ELSE 0 END) as total_credits
    FROM banking_transactions
    WHERE transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
""")
row = cur.fetchone()
if row[0] == 0:
    print("NO 2012 banking data found in banking_transactions")
else:
    print(f"Found: {row[0]:,} transactions")
    print(f"Date range: {row[1]} to {row[2]}")
    print(f"Total debits: ${row[3]:,.2f}")
    print(f"Total credits: ${row[4]:,.2f}")

print("\n=== Checking for account_number field ===")
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name='banking_transactions' 
      AND column_name LIKE '%account%'
""")
for col in cur.fetchall():
    print(f"  {col[0]}")

print("\n=== Checking year coverage in banking_transactions ===")
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        COUNT(*) as count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    GROUP BY year
    ORDER BY year
""")
print(f"{'Year':<8} {'Count':>10} {'First Date':<15} {'Last Date':<15}")
print("-" * 60)
for row in cur.fetchall():
    print(f"{int(row[0]):<8} {row[1]:>10,} {str(row[2]):<15} {str(row[3]):<15}")

cur.close()
conn.close()
