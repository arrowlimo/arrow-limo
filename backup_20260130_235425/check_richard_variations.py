#!/usr/bin/env python3
"""Check both Richard/Michael vendor name variations."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check both variations
cur.execute("""
SELECT DISTINCT
    COALESCE(canonical_vendor, vendor_name) as vendor_name,
    COUNT(*) as cnt,
    SUM(gross_amount) as total,
    gl_account_code
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date) = 2019
AND (COALESCE(canonical_vendor, vendor_name) = 'Michael Richard'
     OR COALESCE(canonical_vendor, vendor_name) = 'Richard Michael')
GROUP BY COALESCE(canonical_vendor, vendor_name), gl_account_code
ORDER BY vendor_name, gl_account_code
""")

print("Vendor Name Variations in 2019:")
print("-" * 80)
for row in cur.fetchall():
    vendor, cnt, total, gl = row
    print(f"{vendor:20} | GL: {str(gl):6} | {cnt:3} receipts | ${total:>10,.2f}")

# Now let's check David Richard too
cur.execute("""
SELECT DISTINCT
    COALESCE(canonical_vendor, vendor_name) as vendor_name,
    COUNT(*) as cnt,
    SUM(gross_amount) as total,
    gl_account_code
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date) = 2019
AND (COALESCE(canonical_vendor, vendor_name) LIKE '%David%'
     OR COALESCE(canonical_vendor, vendor_name) LIKE '%DAVID%')
GROUP BY COALESCE(canonical_vendor, vendor_name), gl_account_code
ORDER BY vendor_name, gl_account_code
""")

print("\nDavid Richard variations in 2019:")
print("-" * 80)
for row in cur.fetchall():
    vendor, cnt, total, gl = row
    print(f"{vendor:20} | GL: {str(gl):6} | {cnt:3} receipts | ${total:>10,.2f}")

conn.close()
