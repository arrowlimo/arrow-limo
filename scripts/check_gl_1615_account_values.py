#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("="*80)
print("ACCOUNT VALUES IN GENERAL_LEDGER WITH '1615'")
print("="*80)

# Get all distinct account values
cur.execute("""
    SELECT 
        account,
        COUNT(*) as count,
        SUM(credit) as total_credits,
        SUM(debit) as total_debits
    FROM general_ledger
    WHERE account LIKE '%1615%'
    GROUP BY account
    ORDER BY count DESC
""")

print(f"\n{'Account':<40} {'Count':<8} {'Credits':<18} {'Debits':<18}")
print("-" * 90)

for row in cur.fetchall():
    account = row[0]
    count = row[1]
    credits = float(row[2] or 0)
    debits = float(row[3] or 0)
    print(f"{account:<40} {count:<8,} ${credits:>15,.2f} ${debits:>15,.2f}")

# Also check distribution_account field
print("\n" + "="*80)
print("DISTRIBUTION_ACCOUNT VALUES WITH '1615'")
print("="*80)

cur.execute("""
    SELECT 
        distribution_account,
        COUNT(*) as count
    FROM general_ledger
    WHERE account LIKE '%1615%'
      AND distribution_account IS NOT NULL
    GROUP BY distribution_account
    ORDER BY count DESC
    LIMIT 20
""")

results = cur.fetchall()
if results:
    print(f"\n{'Distribution Account':<50} {'Count':<8}")
    print("-" * 60)
    for row in results:
        print(f"{row[0]:<50} {row[1]:<8,}")
else:
    print("\nNo distribution_account values found")

# Check account_name field
print("\n" + "="*80)
print("ACCOUNT_NAME VALUES")
print("="*80)

cur.execute("""
    SELECT 
        account_name,
        COUNT(*) as count
    FROM general_ledger
    WHERE account LIKE '%1615%'
      AND account_name IS NOT NULL
    GROUP BY account_name
    ORDER BY count DESC
    LIMIT 20
""")

results = cur.fetchall()
if results:
    print(f"\n{'Account Name':<50} {'Count':<8}")
    print("-" * 60)
    for row in results:
        print(f"{row[0]:<50} {row[1]:<8,}")
else:
    print("\nNo account_name values found")

cur.close()
conn.close()

print("\n" + "="*80)
print("INTERPRETATION: These are all CIBC Bank 1615 transactions")
print("The 'account' field shows the BANK account (where money moved)")
print("="*80)
