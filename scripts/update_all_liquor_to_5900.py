#!/usr/bin/env python3
"""Update all liquor purchases to GL 5900 (Client Beverages)"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

print("\n" + "="*100)
print("UPDATING ALL LIQUOR PURCHASES TO GL 5900 (CLIENT BEVERAGES)")
print("="*100)

# Update all liquor-related receipts to GL 5900
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5900',
        category = 'Client Beverages'
    WHERE (vendor_name ILIKE '%liquor%'
        OR vendor_name ILIKE '%wine%'
        OR vendor_name ILIKE '%beer%'
        OR vendor_name ILIKE '%alcohol%'
        OR canonical_vendor ILIKE '%liquor%'
        OR category ILIKE '%liquor%'
        OR description ILIKE '%liquor%'
        OR description ILIKE '%wine%'
        OR description ILIKE '%alcohol%')
      AND gl_account_code != '5900'
""")

updated = cur.rowcount
print(f"\n✅ Updated {updated:,} receipts to GL 5900 (Client Beverages)")

# Verify results
cur.execute("""
    SELECT 
        gl_account_code,
        COUNT(*) as cnt,
        SUM(COALESCE(gross_amount, 0)) as total
    FROM receipts
    WHERE vendor_name ILIKE '%liquor%'
       OR vendor_name ILIKE '%wine%'
       OR vendor_name ILIKE '%beer%'
       OR vendor_name ILIKE '%alcohol%'
       OR canonical_vendor ILIKE '%liquor%'
       OR category ILIKE '%liquor%'
       OR category ILIKE '%beverage%'
       OR description ILIKE '%liquor%'
       OR description ILIKE '%wine%'
       OR description ILIKE '%alcohol%'
    GROUP BY gl_account_code
    ORDER BY cnt DESC
""")

print("\n" + "="*100)
print("VERIFICATION - LIQUOR PURCHASES BY GL CODE")
print("="*100)
print(f"\n{'GL Code':<10} {'Count':>8}  {'Total':>15}")
print("="*100)

for row in cur.fetchall():
    gl = row[0] or 'NULL'
    cnt = row[1]
    total = row[2]
    status = "✓" if gl == '5900' else "✗"
    print(f"{gl:<10} {cnt:>8,}  ${total:>14,.2f} {status}")

conn.commit()
print("\n✅ Changes committed")

cur.close()
conn.close()
