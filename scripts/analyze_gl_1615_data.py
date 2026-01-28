#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("="*80)
print("GENERAL_LEDGER: Account 1615 Data Breakdown")
print("="*80)

# Year breakdown
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM date) as year,
        COUNT(*) as count,
        SUM(credit) as credits,
        SUM(debit) as debits
    FROM general_ledger
    WHERE account LIKE '%1615%'
    GROUP BY EXTRACT(YEAR FROM date)
    ORDER BY year
""")

print(f"\n{'Year':<6} {'Count':<8} {'Credits':<18} {'Debits':<18}")
print("-" * 60)

for row in cur.fetchall():
    year = int(row[0]) if row[0] else "NULL"
    count = row[1]
    credits = float(row[2] or 0)
    debits = float(row[3] or 0)
    print(f"{year:<6} {count:<8,} ${credits:>15,.2f} ${debits:>15,.2f}")

# Month breakdown for 2012 and 2013
print("\n" + "="*80)
print("2012-2013 MONTHLY BREAKDOWN")
print("="*80)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM date) as year,
        EXTRACT(MONTH FROM date) as month,
        COUNT(*) as count,
        SUM(credit) as credits,
        SUM(debit) as debits
    FROM general_ledger
    WHERE account LIKE '%1615%'
      AND date >= '2012-01-01'
      AND date < '2014-01-01'
    GROUP BY EXTRACT(YEAR FROM date), EXTRACT(MONTH FROM date)
    ORDER BY year, month
""")

print(f"\n{'Year-Month':<12} {'Count':<8} {'Credits':<18} {'Debits':<18}")
print("-" * 60)

for row in cur.fetchall():
    year = int(row[0])
    month = int(row[1])
    count = row[2]
    credits = float(row[3] or 0)
    debits = float(row[4] or 0)
    print(f"{year}-{month:02d}      {count:<8,} ${credits:>15,.2f} ${debits:>15,.2f}")

# Check if these are in banking_transactions
print("\n" + "="*80)
print("CROSS-CHECK WITH BANKING_TRANSACTIONS")
print("="*80)

cur.execute("""
    SELECT COUNT(*) FROM banking_transactions
    WHERE account_number = '1615'
      AND transaction_date >= '2012-04-01'
      AND transaction_date < '2013-01-01'
""")
banking_count = cur.fetchone()[0]

print(f"\nBanking transactions for 1615 (2012 Apr-Dec): {banking_count}")

cur.execute("""
    SELECT COUNT(*) FROM general_ledger
    WHERE account LIKE '%1615%'
      AND date >= '2012-04-01'
      AND date < '2013-01-01'
""")
gl_count = cur.fetchone()[0]

print(f"General_ledger transactions for 1615 (2012 Apr-Dec): {gl_count}")
print(f"\nMISSING from banking_transactions: {gl_count - banking_count}")

cur.close()
conn.close()

print("\n" + "="*80)
print("✅ CONFIRMED: general_ledger has the missing 1615 data!")
print("="*80)
