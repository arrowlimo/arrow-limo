#!/usr/bin/env python3
"""Check if Gursky appears anywhere in receipts."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

# Search for Gursky
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, canonical_vendor, description, gross_amount
    FROM receipts
    WHERE vendor_name ILIKE '%gursky%'
    OR description ILIKE '%gursky%'
    ORDER BY receipt_date DESC
""")

rows = cur.fetchall()
print(f"Found {len(rows)} receipts mentioning Gursky\n")

for row in rows:
    receipt_id, date, vendor, canonical, desc, amount = row
    print(f"ID: {receipt_id} | Date: {date} | ${amount:>8.2f}")
    print(f"  Vendor: {vendor}")
    print(f"  Canonical: {canonical}")
    print(f"  Description: {desc}")
    print()

conn.close()
