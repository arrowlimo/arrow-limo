#!/usr/bin/env python3
"""Check Fibrenew receipts to understand what work was in progress."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("="*120)
print("FIBRENEW RECEIPTS")
print("="*120)

cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, category, 
           gl_account_code, description
    FROM receipts
    WHERE vendor_name ILIKE '%fibrenew%' 
       OR description ILIKE '%fibrenew%'
    ORDER BY receipt_date DESC
    LIMIT 50
""")

print(f"\n{'ID':6s} | Date       | {'Vendor':20s} | Amount    | {'Category':15s} | GL Code | Description")
print("-"*120)
for r in cur.fetchall():
    vendor = (r[2] or "")[:18]
    category = (r[4] or "")[:13]
    gl = r[5] or ""
    desc = (r[6] or "")[:45]
    print(f"{r[0]:6d} | {r[1]} | {vendor:18s} | ${r[3]:>8.2f} | {category:13s} | {gl:7s} | {desc}")

# Check for recent $700 receipts
print("\n" + "="*120)
print("RECENT RECEIPTS NEAR $700")
print("="*120)
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, category, 
           gl_account_code, description
    FROM receipts
    WHERE gross_amount BETWEEN 650 AND 750
    AND receipt_date >= '2025-11-01'
    ORDER BY receipt_date DESC
""")

print(f"\n{'ID':6s} | Date       | {'Vendor':25s} | Amount    | {'Category':15s} | Description")
print("-"*120)
for r in cur.fetchall():
    vendor = (r[2] or "")[:23]
    category = (r[4] or "")[:13]
    desc = (r[6] or "")[:45]
    print(f"{r[0]:6d} | {r[1]} | {vendor:23s} | ${r[3]:>8.2f} | {category:13s} | {desc}")

conn.close()
