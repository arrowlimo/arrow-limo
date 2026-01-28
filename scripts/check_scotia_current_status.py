#!/usr/bin/env python
"""
Check what Scotia 6011 data exists in banking_transactions table.
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

conn = get_db_connection()
cur = conn.cursor()

print("=" * 100)
print("SCOTIA BANK ACCOUNT 903990106011 - CURRENT DATABASE STATUS")
print("=" * 100)

# Check by year
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date)::int as year,
        COUNT(*) as txn_count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        ROUND(MIN(balance)::numeric, 2) as min_balance,
        ROUND(MAX(balance)::numeric, 2) as max_balance,
        ROUND(SUM(COALESCE(debit_amount, 0))::numeric, 2) as total_debits,
        ROUND(SUM(COALESCE(credit_amount, 0))::numeric, 2) as total_credits
    FROM banking_transactions
    WHERE account_number = '903990106011'
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY year
""")

print("\nYEAR-BY-YEAR SUMMARY:")
print("-" * 100)
print(f"{'Year':<6} {'Count':<8} {'First Date':<12} {'Last Date':<12} {'Min Balance':<15} {'Max Balance':<15} {'Total Debits':<15} {'Total Credits':<15}")
print("-" * 100)

rows = cur.fetchall()
if rows:
    for year, cnt, first, last, min_bal, max_bal, debits, credits in rows:
        print(f"{year:<6} {cnt:<8} {first!s:<12} {last!s:<12} ${min_bal:<14.2f} ${max_bal:<14.2f} ${debits:<14.2f} ${credits:<14.2f}")
else:
    print("NO DATA FOUND")

# Total across all years
cur.execute("""
    SELECT 
        COUNT(*) as total_count,
        MIN(transaction_date) as earliest,
        MAX(transaction_date) as latest
    FROM banking_transactions
    WHERE account_number = '903990106011'
""")

total, earliest, latest = cur.fetchone()
print("-" * 100)
print(f"TOTAL: {total} transactions from {earliest} to {latest}")

# Check for specific balance checkpoints
print("\n" + "=" * 100)
print("EXPECTED BALANCE CHECKPOINTS (from user)")
print("=" * 100)

checkpoints = [
    ('2012-01-01', 40.00, "2012 Opening"),
    ('2012-12-31', 952.04, "2012 Closing / 2013 Opening"),
    ('2013-12-31', 6404.87, "2013 Closing"),
    ('2014-01-01', 1839.42, "2014 Opening (user stated)"),
    ('2014-12-31', 4006.29, "2014 Closing"),
]

print(f"\n{'Date':<12} {'Expected':<15} {'Database':<15} {'Status':<10} {'Description':<30}")
print("-" * 100)

for date, expected, desc in checkpoints:
    cur.execute("""
        SELECT balance FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_date = %s
        ORDER BY transaction_id DESC
        LIMIT 1
    """, (date,))
    
    result = cur.fetchone()
    if result:
        actual = float(result[0])
        diff = abs(actual - expected)
        status = "✓ OK" if diff < 0.01 else f"✗ OFF ${diff:.2f}"
        print(f"{date:<12} ${expected:<14.2f} ${actual:<14.2f} {status:<10} {desc:<30}")
    else:
        print(f"{date:<12} ${expected:<14.2f} {'NO DATA':<14} {'✗ MISSING':<10} {desc:<30}")

print("\n" + "=" * 100)

cur.close()
conn.close()
