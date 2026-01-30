#!/usr/bin/env python3
"""Investigate Richard/Michael vendor name variations - likely Gursky."""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

conn = get_db_connection()
cur = conn.cursor()

print("="*80)
print("INVESTIGATING RICHARD/MICHAEL/GURSKY VENDOR NAME VARIATIONS")
print("="*80)

# Find all variations
print("\n1. All unique vendor names containing 'richard', 'michael', or 'gursky':")
print("-"*80)
cur.execute("""
    SELECT DISTINCT COALESCE(canonical_vendor, vendor_name) as vendor
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
    AND (
        COALESCE(canonical_vendor, vendor_name) ILIKE '%richard%'
        OR COALESCE(canonical_vendor, vendor_name) ILIKE '%michael%'
        OR COALESCE(canonical_vendor, vendor_name) ILIKE '%gursky%'
    )
    ORDER BY vendor
""")

vendors = [row[0] for row in cur.fetchall()]
for v in vendors:
    print(f"  - {v}")

# Find count and totals by vendor
print("\n2. Totals by vendor variant:")
print("-"*80)
cur.execute("""
    SELECT 
        COALESCE(canonical_vendor, vendor_name) as vendor,
        COUNT(*) as cnt,
        SUM(gross_amount) as total
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
    AND (
        COALESCE(canonical_vendor, vendor_name) ILIKE '%richard%'
        OR COALESCE(canonical_vendor, vendor_name) ILIKE '%michael%'
        OR COALESCE(canonical_vendor, vendor_name) ILIKE '%gursky%'
    )
    GROUP BY COALESCE(canonical_vendor, vendor_name)
    ORDER BY total DESC
""")

for row in cur.fetchall():
    vendor, cnt, total = row
    print(f"  {vendor:35} | {cnt:3} receipts | ${total:>10,.2f}")

# Look at descriptions to understand pattern
print("\n3. Sample descriptions for 'Richard Michael' (likely truncated Gursky):")
print("-"*80)
cur.execute("""
    SELECT DISTINCT description
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
    AND COALESCE(canonical_vendor, vendor_name) = 'Richard Michael'
    ORDER BY description
    LIMIT 15
""")

for row in cur.fetchall():
    desc = row[0]
    if desc:
        print(f"  {desc[:75]}")

# Look at raw descriptions that mention Gursky
print("\n4. Sample descriptions containing 'Gursky':")
print("-"*80)
cur.execute("""
    SELECT DISTINCT description
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
    AND description ILIKE '%gursky%'
    ORDER BY description
    LIMIT 10
""")

for row in cur.fetchall():
    desc = row[0]
    if desc:
        print(f"  {desc[:75]}")

# Count how many e-transfers mention specific names
print("\n5. E-transfer recipients (from descriptions):")
print("-"*80)
cur.execute("""
    SELECT 
        substring(description FROM 'E-TRANSFER [0-9]+ (.+?)( - |$)') as recipient,
        COUNT(*) as cnt,
        SUM(gross_amount) as total
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
    AND description ILIKE '%E-TRANSFER%'
    AND description ILIKE '%gursky%'
    GROUP BY substring(description FROM 'E-TRANSFER [0-9]+ (.+?)( - |$)')
    ORDER BY total DESC
""")

results = cur.fetchall()
if results:
    for row in results:
        recipient, cnt, total = row
        print(f"  {recipient:30} | {cnt:3} | ${total:>10,.2f}")
else:
    print("  No direct E-TRANSFER patterns found with Gursky")

conn.close()
