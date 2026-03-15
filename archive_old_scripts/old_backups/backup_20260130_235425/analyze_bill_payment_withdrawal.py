#!/usr/bin/env python
"""Analyze BILL PAYMENT and WITHDRAWAL entries."""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "="*100)
print("BILL PAYMENT - DETAILS (should have vendor names like telus, shaw)")
print("="*100)

cur.execute("""
    SELECT receipt_date, gross_amount, description
    FROM receipts
    WHERE vendor_name = 'BILL PAYMENT' AND gl_account_code = '9999'
    ORDER BY receipt_date DESC
""")

rows = cur.fetchall()
print(f"\nFound {len(rows)} BILL PAYMENT entries\n")
for row in rows:
    print(f"{row[0]} | ${row[1]:>10.2f} | {row[2]}")

print("\n" + "="*100)
print("WITHDRAWAL IBB - DETAILS (bank withdrawals → GL 3650)")
print("="*100)

cur.execute("""
    SELECT receipt_date, gross_amount, description
    FROM receipts
    WHERE vendor_name = 'WITHDRAWAL IBB' AND gl_account_code = '9999'
    ORDER BY receipt_date DESC
""")

rows = cur.fetchall()
print(f"\nFound {len(rows)} WITHDRAWAL IBB entries (total ${sum(float(r[1]) for r in rows):,.2f})\n")
for row in rows:
    print(f"{row[0]} | ${row[1]:>10.2f} | {row[2]}")

cur.close()
conn.close()
