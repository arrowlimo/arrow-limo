#!/usr/bin/env python3
"""
Identify transactions in 0228362 that actually belong to account 1615
Look at source files and patterns to determine which account they came from
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*80)
print("IDENTIFYING 1615 TRANSACTIONS IN ACCOUNT 0228362")
print("="*80)

# Check source files for both accounts
print("\nSource files for account 1615:")
cur.execute("""
    SELECT DISTINCT source_file, COUNT(*)
    FROM banking_transactions
    WHERE account_number = '1615'
    GROUP BY source_file
    ORDER BY COUNT(*) DESC
""")

source_1615 = []
for row in cur.fetchall():
    source = row[0] or 'NULL'
    count = row[1]
    print(f"  {source}: {count} transactions")
    source_1615.append(source)

print("\n" + "-"*80)
print("\nSource files for account 0228362 (2012-2017 only):")
cur.execute("""
    SELECT DISTINCT source_file, COUNT(*)
    FROM banking_transactions
    WHERE account_number = '0228362'
      AND EXTRACT(YEAR FROM transaction_date) BETWEEN 2012 AND 2017
    GROUP BY source_file
    ORDER BY COUNT(*) DESC
""")

for row in cur.fetchall():
    source = row[0] or 'NULL'
    count = row[1]
    marker = " ⚠️  MATCHES 1615 SOURCE" if source in source_1615 else ""
    print(f"  {source}: {count} transactions{marker}")

# Check if there are transactions in 0228362 from "unified_general_ledger:1000 CIBC Bank 1615"
print("\n" + "="*80)
print("CHECKING FOR 1615 TRANSACTIONS IN 0228362")
print("="*80)

cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE account_number = '0228362'
      AND source_file LIKE '%1615%'
""")

count_1615_in_0228362 = cur.fetchone()[0]

if count_1615_in_0228362 > 0:
    print(f"\n⚠️  Found {count_1615_in_0228362} transactions in 0228362 with '1615' in source_file!")
    
    # Show details
    cur.execute("""
        SELECT source_file, 
               EXTRACT(YEAR FROM transaction_date) as year,
               COUNT(*)
        FROM banking_transactions
        WHERE account_number = '0228362'
          AND source_file LIKE '%1615%'
        GROUP BY source_file, EXTRACT(YEAR FROM transaction_date)
        ORDER BY year, source_file
    """)
    
    print(f"\nBreakdown:")
    print(f"{'Source File':<60} {'Year':<6} {'Count':<10}")
    print("-" * 80)
    
    for row in cur.fetchall():
        print(f"{row[0]:<60} {int(row[1]):<6} {row[2]:<10}")
    
    print(f"\n{'='*80}")
    print("RECOMMENDATION: Move these transactions from 0228362 to 1615")
    print("="*80)
    
else:
    print(f"\n✅ No transactions in 0228362 have '1615' in source_file")
    
    # Check for other patterns
    print("\nChecking for transactions that might belong to 1615 based on patterns...")
    
    # Get sample transactions from each account to compare patterns
    cur.execute("""
        SELECT transaction_date, description, debit_amount, credit_amount, source_file
        FROM banking_transactions
        WHERE account_number = '1615'
        ORDER BY transaction_date
        LIMIT 5
    """)
    
    print("\nSample transactions in 1615:")
    for row in cur.fetchall():
        print(f"  {row[0]} | {row[1][:40]:<40} | {row[4] or 'NULL'}")

# Check description patterns
print("\n" + "="*80)
print("CHECKING DESCRIPTION PATTERNS")
print("="*80)

# See if there are unique description patterns in 1615
cur.execute("""
    SELECT description, COUNT(*)
    FROM banking_transactions
    WHERE account_number = '1615'
    GROUP BY description
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    LIMIT 10
""")

print("\nCommon descriptions in account 1615:")
for row in cur.fetchall():
    desc = row[0]
    count = row[1]
    
    # Check if this description exists in 0228362
    cur.execute("""
        SELECT COUNT(*)
        FROM banking_transactions
        WHERE account_number = '0228362'
          AND description = %s
          AND EXTRACT(YEAR FROM transaction_date) BETWEEN 2012 AND 2017
    """, (desc,))
    
    count_in_0228362 = cur.fetchone()[0]
    
    if count_in_0228362 > 0:
        print(f"  {desc[:50]:<50} | In 1615: {count:>4} | In 0228362: {count_in_0228362:>4} ⚠️")

cur.close()
conn.close()

print("\n" + "="*80)
print("Next: If transactions identified, create script to move them")
print("="*80)
