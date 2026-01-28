#!/usr/bin/env python3
"""
Calculate total NSF (Non-Sufficient Funds) fees paid.
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Find all NSF-related receipts
cur.execute("""
    SELECT 
        COUNT(*) as count,
        SUM(gross_amount) as total_amount,
        MIN(receipt_date) as earliest,
        MAX(receipt_date) as latest
    FROM receipts
    WHERE vendor_name ILIKE '%NSF%'
""")

result = cur.fetchone()
count, total, earliest, latest = result

print("=" * 80)
print("NSF (NON-SUFFICIENT FUNDS) PAYMENTS SUMMARY")
print("=" * 80)
print(f"Total NSF transactions: {count:,}")
if total:
    print(f"Total NSF fees paid: ${total:,.2f}")
else:
    print("Total NSF fees paid: $0.00")
if earliest:
    print(f"Date range: {earliest} to {latest}")
print()

# Get breakdown by year
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM receipt_date) as year,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE vendor_name ILIKE '%NSF%'
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY year
""")

print("NSF FEES BY YEAR:")
print("-" * 80)
for row in cur.fetchall():
    year, cnt, amt = row
    print(f"{int(year)}: {cnt:3} transactions = ${amt:10,.2f}")

print()
print("=" * 80)

# Show some examples
cur.execute("""
    SELECT 
        receipt_date,
        vendor_name,
        gross_amount,
        CASE WHEN mapped_bank_account_id = 1 THEN 'CIBC' 
             WHEN mapped_bank_account_id = 2 THEN 'Scotia'
             ELSE 'Unknown' END as bank
    FROM receipts
    WHERE vendor_name ILIKE '%NSF%'
    ORDER BY receipt_date DESC
    LIMIT 20
""")

print("RECENT NSF TRANSACTIONS (Last 20):")
print("-" * 80)
for row in cur.fetchall():
    date, vendor, amount, bank = row
    print(f"{date} | {bank:6} | ${amount:8,.2f} | {vendor}")

cur.close()
conn.close()
