#!/usr/bin/env python3
"""Update remaining NULL liquor receipts"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

# Update remaining receipts
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5900',
        category = 'Client Beverages'
    WHERE (vendor_name ILIKE '%liquor%'
        OR vendor_name ILIKE '%wine%'
        OR vendor_name ILIKE '%beer%'
        OR canonical_vendor ILIKE '%liquor%')
      AND (gl_account_code IS NULL OR gl_account_code != '5900')
""")

print(f"✅ Updated {cur.rowcount} remaining liquor receipts to GL 5900")

conn.commit()
print("✅ Committed")

cur.close()
conn.close()
