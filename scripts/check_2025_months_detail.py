#!/usr/bin/env python3
"""Check which specific months exist for CIBC 0228362 in 2025."""
import psycopg2

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REMOVED***', host='localhost')
cur = conn.cursor()

print("=" * 80)
print("CIBC ACCOUNT 0228362 - 2025 MONTHLY DETAIL")
print("=" * 80)
print()

cur.execute("""
    SELECT 
        EXTRACT(MONTH FROM transaction_date)::INT as month,
        COUNT(*) as tx_count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE account_number LIKE '%0228362%'
    AND EXTRACT(YEAR FROM transaction_date) = 2025
    GROUP BY EXTRACT(MONTH FROM transaction_date)
    ORDER BY month
""")

rows = cur.fetchall()
months_present = set()
month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

print(f"{'Month':10} | {'Count':>6} | {'First Date':12} | {'Last Date':12}")
print("-" * 55)

for month, count, first_date, last_date in rows:
    months_present.add(month)
    print(f"{month_names[month]:10} | {count:6,} | {first_date} | {last_date}")

print()
print("=" * 80)

all_months = set(range(1, 13))
missing_months = all_months - months_present

if missing_months:
    missing_names = [month_names[m] for m in sorted(missing_months)]
    print(f"MISSING MONTHS: {', '.join(missing_names)}")
    
    # Check if we have data in other accounts
    for month in sorted(missing_months):
        print(f"\n{month_names[month]} 2025 - checking other CIBC accounts:")
        cur.execute("""
            SELECT account_number, COUNT(*) as cnt
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = 2025
            AND EXTRACT(MONTH FROM transaction_date) = %s
            AND (account_number LIKE '%CIBC%' OR account_number IN ('8314462', '3648117'))
            GROUP BY account_number
            ORDER BY cnt DESC
        """, (month,))
        other_data = cur.fetchall()
        if other_data:
            for acct, cnt in other_data:
                print(f"  {acct}: {cnt:,} transactions")
        else:
            print(f"  No CIBC data found for {month_names[month]} 2025 in any account")
else:
    print("✓ All 12 months present!")

conn.close()
