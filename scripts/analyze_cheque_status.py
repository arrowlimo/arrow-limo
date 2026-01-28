#!/usr/bin/env python3
"""Analyze CHEQUE receipts and identify verification needs."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("=" * 100)
print("CHEQUE RECEIPT ANALYSIS")
print("=" * 100)

# Find all CHEQUE receipts
cur.execute("""
    SELECT vendor_name, COUNT(*) as count, SUM(gross_amount) as total
    FROM receipts
    WHERE vendor_name LIKE '%CHEQUE%'
    GROUP BY vendor_name
    ORDER BY total DESC
""")

cheque_vendors = cur.fetchall()
print(f"\nCHEQUE VENDOR BREAKDOWN ({sum(c[1] for c in cheque_vendors)} total):\n")

for vendor, count, total in cheque_vendors:
    print(f"{vendor:40} | {count:4d} receipts | ${total:12,.2f}")

print("\n" + "=" * 100)
print("LARGE CHEQUE AMOUNTS (>$100K)")
print("=" * 100 + "\n")

cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, receipt_date, description
    FROM receipts
    WHERE vendor_name LIKE '%CHEQUE%'
    AND gross_amount > 100000
    ORDER BY gross_amount DESC
""")

large_cheques = cur.fetchall()

if large_cheques:
    for receipt_id, vendor, amount, date, desc in large_cheques:
        print(f"Receipt {receipt_id}")
        print(f"  Vendor: {vendor}")
        print(f"  Amount: ${amount:,.2f}")
        print(f"  Date: {date}")
        print(f"  Desc: {desc}")
        print()
else:
    print("No large cheques found")

print("=" * 100)
print("CHEQUE RECEIPTS WITH NULL BANKING LINK")
print("=" * 100 + "\n")

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name LIKE '%CHEQUE%'
    AND banking_transaction_id IS NULL
""")

orphan_count, orphan_total = cur.fetchone()
print(f"Orphan CHEQUE receipts: {orphan_count} totaling ${orphan_total:,.2f}\n")

# Sample orphans
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, receipt_date, description
    FROM receipts
    WHERE vendor_name LIKE '%CHEQUE%'
    AND banking_transaction_id IS NULL
    ORDER BY receipt_date DESC
    LIMIT 10
""")

print("Sample orphan CHEQUE receipts:\n")
for receipt_id, vendor, amount, date, desc in cur.fetchall():
    print(f"Receipt {receipt_id} | {date} | ${amount:,.2f}")
    print(f"  Vendor: {vendor}")
    print(f"  Desc: {desc}")
    print()

cur.close()
conn.close()

print("✅ Analysis complete")
