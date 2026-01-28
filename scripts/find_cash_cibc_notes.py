#!/usr/bin/env python3
"""Find receipts with vendor names containing cash/cibc/combined/money notes."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)

cur = conn.cursor()

# Search for receipts with notes about cash/cibc/combined transactions
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
    FROM receipts
    WHERE (
        LOWER(vendor_name) LIKE '%cash%' 
        OR LOWER(vendor_name) LIKE '%cibc%' 
        OR LOWER(vendor_name) LIKE '%combined%' 
        OR LOWER(vendor_name) LIKE '%money%'
    )
    AND receipt_date BETWEEN '2012-01-01' AND '2012-12-31'
    ORDER BY receipt_date
""")

rows = cur.fetchall()
print(f"\nFound {len(rows)} receipts with cash/cibc/combined/money in vendor name (2012):\n")
print(f"{'ID':>6} | {'Date':>10} | {'Vendor':50} | {'Amount':>12} | Description")
print("-" * 140)

for r in rows:
    desc = (r[4][:60] if r[4] else "")
    print(f"{r[0]:6} | {r[1]} | {r[2]:50} | ${r[3]:>10.2f} | {desc}")

cur.close()
conn.close()
