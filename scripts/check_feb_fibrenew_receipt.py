#!/usr/bin/env python3
"""Check for $300 Fibrenew receipt #0534 from Feb 20, 2024."""

import psycopg2
import os

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check for Feb 2024 Fibrenew receipts
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description, category
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%fibrenew%'
    AND receipt_date BETWEEN '2024-02-01' AND '2024-02-29'
    ORDER BY receipt_date
""")

feb_receipts = cur.fetchall()
print("February 2024 Fibrenew receipts:")
for r in feb_receipts:
    print(f"{r[0]:6} | {r[1]} | ${r[3]:>8,.2f} | {r[4][:60]}")

# Check for $300 on Feb 20, 2024 (any vendor)
print("\n$300 receipts on Feb 20, 2024:")
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
    FROM receipts
    WHERE receipt_date = '2024-02-20'
    AND gross_amount = 300
""")

results = cur.fetchall()
if results:
    for r in results:
        print(f"{r[0]:6} | {r[1]} | {r[2]:20} | ${r[3]:>8,.2f} | {r[4][:50]}")
else:
    print("No $300 receipt found on Feb 20, 2024")

# Check if invoice #0534 exists
print("\nSearching for invoice/receipt #0534:")
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
    FROM receipts
    WHERE description LIKE '%0534%' OR description LIKE '%534%'
""")

results = cur.fetchall()
if results:
    for r in results:
        print(f"{r[0]:6} | {r[1]} | {r[2]:20} | ${r[3]:>8,.2f} | {r[4]}")
else:
    print("No receipt with #0534 found")

cur.close()
conn.close()
