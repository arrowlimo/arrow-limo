#!/usr/bin/env python3
"""
Compare accounts 0228362 and 1615 to understand the data separation
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*80)
print("ACCOUNTS 0228362 vs 1615 - YEAR BY YEAR COMPARISON")
print("="*80)

# Get yearly breakdown for both accounts
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        SUM(CASE WHEN account_number = '0228362' THEN 1 ELSE 0 END) as count_0228362,
        SUM(CASE WHEN account_number = '1615' THEN 1 ELSE 0 END) as count_1615
    FROM banking_transactions
    WHERE account_number IN ('0228362', '1615')
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY year
""")

print(f"\n{'Year':<6} {'0228362':<12} {'1615':<12} {'Notes':<30}")
print("-" * 70)

for row in cur.fetchall():
    year = int(row[0])
    count_0228362 = row[1]
    count_1615 = row[2]
    
    note = ""
    if count_1615 > 0 and count_0228362 > 0:
        note = "⚠️  BOTH ACCOUNTS ACTIVE"
    elif count_1615 > 0:
        note = "Only 1615"
    elif count_0228362 > 0:
        note = "Only 0228362"
    
    print(f"{year:<6} {count_0228362:<12} {count_1615:<12} {note:<30}")

# Check date ranges
print("\n" + "="*80)
print("DATE RANGES")
print("="*80)

cur.execute("""
    SELECT account_number,
           MIN(transaction_date) as first_date,
           MAX(transaction_date) as last_date,
           COUNT(*) as total
    FROM banking_transactions
    WHERE account_number IN ('0228362', '1615')
    GROUP BY account_number
""")

for row in cur.fetchall():
    print(f"\nAccount {row[0]}:")
    print(f"  First transaction: {row[1]}")
    print(f"  Last transaction: {row[2]}")
    print(f"  Total transactions: {row[3]:,}")

# Check 2020 onwards overlap
print("\n" + "="*80)
print("2020 ONWARDS - POTENTIAL OVERLAP")
print("="*80)

cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE account_number = '1615'
      AND EXTRACT(YEAR FROM transaction_date) >= 2020
    ORDER BY transaction_date
    LIMIT 10
""")

rows_1615_2020 = cur.fetchall()
if rows_1615_2020:
    print(f"\n⚠️  WARNING: Account 1615 has transactions from 2020 onwards!")
    print(f"\nFirst 10 transactions in 1615 from 2020+:")
    for row in rows_1615_2020:
        debit = f"${row[2]:,.2f}" if row[2] else ""
        credit = f"${row[3]:,.2f}" if row[3] else ""
        print(f"  {row[0]} | {row[1][:50]:<50} | D:{debit:>10} C:{credit:>10}")
else:
    print("\n✅ Account 1615 has NO transactions from 2020 onwards")
    print("   All 2020+ data is correctly in account 0228362")

# Summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)

cur.execute("""
    SELECT COUNT(*) FROM banking_transactions
    WHERE account_number = '1615'
      AND EXTRACT(YEAR FROM transaction_date) >= 2020
""")
count_1615_2020_plus = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*) FROM banking_transactions
    WHERE account_number = '0228362'
      AND EXTRACT(YEAR FROM transaction_date) >= 2020
""")
count_0228362_2020_plus = cur.fetchone()[0]

print(f"\n2020+ Transactions:")
print(f"  Account 0228362: {count_0228362_2020_plus:,}")
print(f"  Account 1615: {count_1615_2020_plus:,}")

if count_1615_2020_plus > 0:
    print(f"\n⚠️  Account 1615 should only have old data (2012-2017)")
    print(f"   But it has {count_1615_2020_plus} transactions from 2020+")
    print(f"   These may be from QuickBooks GL and should stay separate")

cur.close()
conn.close()
