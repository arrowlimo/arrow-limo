#!/usr/bin/env python3
"""Check what vendor extraction work was actually committed."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)
cur = conn.cursor()

print("CHECKING WHAT WAS ACTUALLY SAVED TO DATABASE")
print("=" * 80)

# Check POINT OF with descriptions
cur.execute("""
    SELECT COUNT(*) 
    FROM receipts 
    WHERE vendor_name = 'POINT OF'
      AND description IS NOT NULL
      AND description != ''
""")
point_of_with_desc = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*) 
    FROM receipts 
    WHERE vendor_name = 'POINT OF'
""")
total_point_of = cur.fetchone()[0]

print(f"\nPOINT OF receipts: {total_point_of:,}")
print(f"  With description: {point_of_with_desc:,}")
print(f"  Without description: {total_point_of - point_of_with_desc:,}")

# Show sample with descriptions
print("\nSample POINT OF receipts WITH descriptions:")
cur.execute("""
    SELECT receipt_id, description
    FROM receipts
    WHERE vendor_name = 'POINT OF'
      AND description LIKE '%RETAIL PURCHASE%'
    LIMIT 10
""")

for receipt_id, desc in cur.fetchall():
    # Extract vendor from description
    import re
    match = re.search(r'RETAIL PURCHASE\s+\d+\s+(.+?)(?:\s+RED\s+DE|\s*$)', desc)
    if match:
        vendor = match.group(1).strip()
        print(f"  {receipt_id}: {desc[:60]}")
        print(f"    → Extracted: {vendor}")

print("\n\n🔍 THE VENDOR NAMES ARE IN THE DESCRIPTION COLUMN!")
print("We need to extract them from description and update vendor_name")

cur.close()
conn.close()
