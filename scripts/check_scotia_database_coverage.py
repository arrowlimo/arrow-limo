"""Check Scotia Bank database coverage and identify gaps."""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REDACTED***",
    host="localhost"
)

cur = conn.cursor()

print("="*80)
print("SCOTIA BANK DATABASE COVERAGE ANALYSIS")
print("="*80)
print()

# Overall stats
cur.execute("""
    SELECT 
        COUNT(*) as total_txns,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        COUNT(CASE WHEN balance IS NULL THEN 1 END) as null_balances,
        COUNT(CASE WHEN balance IS NOT NULL THEN 1 END) as have_balances
    FROM banking_transactions
    WHERE account_number = '903990106011'
""")
total, first, last, null_bal, have_bal = cur.fetchone()

print(f"Total Transactions: {total:,}")
print(f"Date Range: {first} to {last}")
print(f"NULL Balances: {null_bal:,} ({null_bal/total*100:.1f}%)")
print(f"Have Balances: {have_bal:,} ({have_bal/total*100:.1f}%)")
print()

# Monthly breakdown for 2012
print("="*80)
print("2012 MONTHLY BREAKDOWN")
print("="*80)
print()
print(f"{'Month':<10} {'Transactions':>13} {'Null Bal':>10} {'Have Bal':>10}")
print("-"*50)

cur.execute("""
    SELECT 
        TO_CHAR(transaction_date, 'YYYY-MM') as month,
        COUNT(*) as txn_count,
        COUNT(CASE WHEN balance IS NULL THEN 1 END) as null_bal,
        COUNT(CASE WHEN balance IS NOT NULL THEN 1 END) as have_bal
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY TO_CHAR(transaction_date, 'YYYY-MM')
    ORDER BY month
""")

total_2012 = 0
for month, count, null_bal, have_bal in cur.fetchall():
    print(f"{month:<10} {count:>13,} {null_bal:>10,} {have_bal:>10,}")
    total_2012 += count

print("-"*50)
print(f"{'2012 Total':<10} {total_2012:>13,}")
print()

# Sample transactions with balance to see what's there
print("="*80)
print("SAMPLE TRANSACTIONS WITH BALANCE (2012)")
print("="*80)
print()

cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    AND balance IS NOT NULL
    ORDER BY transaction_date
    LIMIT 20
""")

print(f"{'Date':<12} {'Description':<40} {'Debit':>10} {'Credit':>10} {'Balance':>12}")
print("-"*90)
for date, desc, debit, credit, bal in cur.fetchall():
    desc = (desc[:37] + '...') if desc and len(desc) > 40 else (desc or '')
    debit_str = f"${debit:,.2f}" if debit else ""
    credit_str = f"${credit:,.2f}" if credit else ""
    bal_str = f"${bal:,.2f}" if bal else ""
    print(f"{date!s:<12} {desc:<40} {debit_str:>10} {credit_str:>10} {bal_str:>12}")

print()
print("="*80)
print("RECOMMENDATION")
print("="*80)
print()
print("Since you already have 4,396 Scotia transactions in the database,")
print("the PDF is likely for VERIFICATION, not primary data entry.")
print()
print("Recommended approach:")
print("1. Export database transactions for 2012 to CSV")
print("2. Manually compare key transactions against PDF")
print("3. Fix specific issues rather than re-extracting from corrupted PDF")
print()

cur.close()
conn.close()
