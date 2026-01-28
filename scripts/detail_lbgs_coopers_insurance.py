#!/usr/bin/env python
"""Get detailed info on LBG'S, CO OPERATORS, and CO-OP INSURANCE."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# First, get column names
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='receipts' ORDER BY ordinal_position")
cols = [row[0] for row in cur.fetchall()]
print("Receipt columns:", cols)
print()

print("\n" + "="*120)
print("DETAILED LOOKUP: LBG'S")
print("="*120)
cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, vendor_name, description, gl_account_code
    FROM receipts
    WHERE UPPER(vendor_name) LIKE '%LBG%'
    ORDER BY receipt_date DESC
""")
rows = cur.fetchall()
print(f"Found {len(rows)} receipt(s):\n")
for receipt_id, receipt_date, gross_amount, vendor, desc, gl_code in rows:
    print(f"  Receipt ID: {receipt_id}")
    print(f"  Date: {receipt_date}")
    print(f"  Amount: ${gross_amount:.2f}")
    print(f"  Vendor: {vendor}")
    print(f"  Description: {desc}")
    print(f"  GL Code: {gl_code}")
    print()

print("\n" + "="*120)
print("DETAILED LOOKUP: CO OPERATORS")
print("="*120)
cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, vendor_name, description, gl_account_code
    FROM receipts
    WHERE UPPER(vendor_name) = 'CO OPERATORS'
    ORDER BY receipt_date DESC
""")
rows = cur.fetchall()
print(f"Found {len(rows)} receipt(s):\n")
for receipt_id, receipt_date, gross_amount, vendor, desc, gl_code in rows:
    print(f"  Receipt ID: {receipt_id}")
    print(f"  Date: {receipt_date}")
    print(f"  Amount: ${gross_amount:.2f}")
    print(f"  Vendor: {vendor}")
    print(f"  Description: {desc}")
    print(f"  GL Code: {gl_code}")
    print()

print("\n" + "="*120)
print("DETAILED LOOKUP: CO-OP INSURANCE (ALL VARIATIONS)")
print("="*120)
cur.execute("""
    SELECT UPPER(vendor_name) AS name, COUNT(*) as cnt,
           STRING_AGG(DISTINCT description, ' | ') as descs,
           STRING_AGG(DISTINCT gl_account_code, ', ') as gl_codes
    FROM receipts
    WHERE UPPER(vendor_name) LIKE '%CO-OP INSURANCE%' OR UPPER(vendor_name) LIKE '%CO OP INSURANCE%' OR UPPER(vendor_name) LIKE '%COOP INSURANCE%'
    GROUP BY 1 ORDER BY 2 DESC
""")
rows = cur.fetchall()
print(f"Found variations:\n")
for name, count, descs, gl_codes in rows:
    print(f"  Vendor Name: {name}")
    print(f"  Count: {count}")
    print(f"  Descriptions: {(descs[:150] + '...') if descs and len(descs) > 150 else descs}")
    print(f"  GL Codes: {gl_codes}")
    print()

# Get sample receipts for CO-OP INSURANCE
print("\n" + "="*120)
print("SAMPLE RECEIPTS: CO-OP INSURANCE")
print("="*120)
cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, vendor_name, description, gl_account_code
    FROM receipts
    WHERE UPPER(vendor_name) LIKE '%CO-OP INSURANCE%' OR UPPER(vendor_name) LIKE '%CO OP INSURANCE%' OR UPPER(vendor_name) LIKE '%COOP INSURANCE%'
    ORDER BY receipt_date DESC
    LIMIT 5
""")
rows = cur.fetchall()
for receipt_id, receipt_date, gross_amount, vendor, desc, gl_code in rows:
    print(f"  Receipt ID: {receipt_id}")
    print(f"  Date: {receipt_date}")
    print(f"  Amount: ${gross_amount:.2f}")
    print(f"  Vendor: {vendor}")
    print(f"  Description: {desc}")
    print(f"  GL Code: {gl_code}")
    print()

cur.close()
conn.close()
