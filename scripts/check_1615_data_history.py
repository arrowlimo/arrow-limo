#!/usr/bin/env python3
"""
Check current state of 1615 data vs December 4 report
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("="*80)
print("CHECKING 1615 DATA - CURRENT VS DECEMBER 4 REPORT")
print("="*80)

# Current state
cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE account_number = '1615'")
current_total = cur.fetchone()[0]

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        COUNT(*) as count
    FROM banking_transactions
    WHERE account_number = '1615'
    GROUP BY year
    ORDER BY year
""")
year_breakdown = cur.fetchall()

print(f"\n**CURRENT DATABASE STATE:**")
print(f"Total 1615 transactions: {current_total:,}")
print(f"\nYear breakdown:")
for row in year_breakdown:
    year = int(row[0]) if row[0] else "NULL"
    count = row[1]
    print(f"  {year}: {count:,}")

# December 4 report said:
print(f"\n**DECEMBER 4, 2025 REPORT CLAIMED:**")
print(f"Total 1615 transactions for 2012: 79")
print(f"Date range: 2012-01-01 to 2012-12-31")
print(f"Source: import_2012_complete_year_verified.py")

# Find 2012 data
cur.execute("""
    SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date)
    FROM banking_transactions
    WHERE account_number = '1615'
      AND EXTRACT(YEAR FROM transaction_date) = 2012
""")
result = cur.fetchone()

print(f"\n**ACTUAL 2012 DATA IN DATABASE RIGHT NOW:**")
print(f"2012 count: {result[0]:,}")
print(f"Date range: {result[1]} to {result[2]}")

# Check source_file patterns
cur.execute("""
    SELECT source_file, COUNT(*)
    FROM banking_transactions
    WHERE account_number = '1615'
    GROUP BY source_file
    ORDER BY COUNT(*) DESC
""")

print(f"\n**SOURCE FILES FOR 1615 DATA:**")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]:,} transactions")

# Check if today's import is there
cur.execute("""
    SELECT COUNT(*), source_file
    FROM banking_transactions
    WHERE account_number = '1615'
      AND source_file LIKE '%general_ledger%'
    GROUP BY source_file
""")

gl_import = cur.fetchall()
if gl_import:
    print(f"\n**TODAY'S GENERAL_LEDGER IMPORT (2025-12-16):**")
    for row in gl_import:
        print(f"  {row[1]}: {row[0]:,} transactions")
else:
    print(f"\n❌ NO GENERAL_LEDGER IMPORT FOUND FROM TODAY")

cur.close()
conn.close()

print("\n" + "="*80)
print("ANALYSIS: Checking if Dec 4 data was overwritten by today's import")
print("="*80)
