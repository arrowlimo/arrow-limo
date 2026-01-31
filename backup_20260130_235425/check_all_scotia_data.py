#!/usr/bin/env python3
"""Check all Scotia Bank data in almsdata database."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("\n" + "="*80)
print("SCOTIA BANK DATA CHECK")
print("="*80)

# Check by account number 3714081
cur.execute("""
    SELECT 
        COUNT(*) as count,
        MIN(transaction_date) as earliest,
        MAX(transaction_date) as latest,
        SUM(COALESCE(debit_amount, 0)) as total_debits,
        SUM(COALESCE(credit_amount, 0)) as total_credits
    FROM banking_transactions
    WHERE account_number = '3714081'
""")

result = cur.fetchone()
if result and result[0] > 0:
    count, earliest, latest, debits, credits = result
    print(f"\nAccount 3714081:")
    print(f"  Total Rows: {count:,}")
    print(f"  Date Range: {earliest} to {latest}")
    print(f"  Total Debits: ${debits:,.2f}")
    print(f"  Total Credits: ${credits:,.2f}")
    print(f"  Net: ${credits - debits:,.2f}")
else:
    print("\nAccount 3714081: NO DATA FOUND")

# Check for any Scotia-related descriptions
cur.execute("""
    SELECT 
        COUNT(*) as count,
        account_number,
        MIN(transaction_date) as earliest,
        MAX(transaction_date) as latest
    FROM banking_transactions
    WHERE description ILIKE '%scotia%'
    GROUP BY account_number
""")

scotia_desc = cur.fetchall()
if scotia_desc:
    print("\n\nTransactions with 'scotia' in description:")
    for row in scotia_desc:
        print(f"  Account {row[1]}: {row[0]} rows ({row[2]} to {row[3]})")
else:
    print("\n\nNo transactions with 'scotia' in description")

# Check 2012 specifically
cur.execute("""
    SELECT 
        TO_CHAR(transaction_date, 'YYYY-MM') as month,
        COUNT(*) as count,
        SUM(COALESCE(debit_amount, 0)) as debits,
        SUM(COALESCE(credit_amount, 0)) as credits
    FROM banking_transactions
    WHERE account_number = '3714081'
    AND transaction_date >= '2012-01-01'
    AND transaction_date < '2013-01-01'
    GROUP BY month
    ORDER BY month
""")

results_2012 = cur.fetchall()
if results_2012:
    print("\n\n2012 Monthly Breakdown (Account 3714081):")
    print("-" * 80)
    total_rows = 0
    total_debits = 0
    total_credits = 0
    for row in results_2012:
        month, count, debits, credits = row
        total_rows += count
        total_debits += debits
        total_credits += credits
        print(f"  {month}: {count:4d} rows | Debits: ${debits:>12,.2f} | Credits: ${credits:>12,.2f}")
    print("-" * 80)
    print(f"  TOTAL: {total_rows:4d} rows | Debits: ${total_debits:>12,.2f} | Credits: ${total_credits:>12,.2f}")
else:
    print("\n\n2012: NO DATA for account 3714081")

# Check all account numbers in banking_transactions
cur.execute("""
    SELECT DISTINCT account_number, COUNT(*)
    FROM banking_transactions
    GROUP BY account_number
    ORDER BY COUNT(*) DESC
""")

print("\n\nAll Account Numbers in banking_transactions:")
print("-" * 80)
for row in cur.fetchall()[:20]:
    print(f"  {row[0]}: {row[1]:,} rows")

cur.close()
conn.close()

print("\n" + "="*80)
