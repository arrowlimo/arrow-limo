#!/usr/bin/env python3
"""
Update VANESSA THOMAS receipts to HEFFNER AUTO FINANCE.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Find VANESSA THOMAS receipts
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, canonical_vendor, gross_amount, revenue, expense
    FROM receipts
    WHERE vendor_name ILIKE '%vanessa thomas%' OR canonical_vendor ILIKE '%vanessa thomas%'
""")
rows = cur.fetchall()

print(f"Found {len(rows)} receipts with VANESSA THOMAS:")
for row in rows:
    rid, rdate, vendor, canonical, gross, revenue, expense = row
    print(f"  ID {rid}: {rdate} | {vendor} | canonical={canonical} | gross=${gross} revenue=${revenue} expense=${expense}")

if rows:
    print("\nUpdating vendor_name and canonical_vendor to HEFFNER AUTO FINANCE...")
    cur.execute("""
        UPDATE receipts
        SET vendor_name = 'HEFFNER AUTO FINANCE',
            canonical_vendor = 'HEFFNER AUTO FINANCE'
        WHERE vendor_name ILIKE '%vanessa thomas%' OR canonical_vendor ILIKE '%vanessa thomas%'
    """)
    print(f"✅ Updated {cur.rowcount} receipts")
    conn.commit()
else:
    print("No receipts to update")

cur.close()
conn.close()
