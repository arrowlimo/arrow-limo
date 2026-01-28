#!/usr/bin/env python3
"""Check if employees table has address columns."""
import os
import psycopg2

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("EMPLOYEES TABLE - ALL COLUMNS:")
print("="*60)
cur.execute("""
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns 
    WHERE table_name = 'employees' 
    ORDER BY ordinal_position
""")

address_related = []
for row in cur.fetchall():
    col_name, data_type, max_len = row
    print(f"{col_name:<40} {data_type}")
    
    # Check if address-related
    if any(keyword in col_name.lower() for keyword in ['address', 'street', 'city', 'postal', 'province', 'country', 'zip']):
        address_related.append(col_name)

print("\n" + "="*60)
if address_related:
    print(f"[OK] Found {len(address_related)} address-related columns:")
    for col in address_related:
        print(f"   - {col}")
else:
    print("[FAIL] No address columns found in employees table")

print("\n" + "="*60)
print("STAGING EMPLOYEE REFERENCE DATA - ADDRESS COLUMNS:")
print("="*60)
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns 
    WHERE table_name = 'staging_employee_reference_data'
    AND column_name IN ('street1', 'city', 'postal_code', 'main_phone')
    ORDER BY ordinal_position
""")

for row in cur.fetchall():
    print(f"{row[0]:<40} {row[1]}")

print("\n" + "="*60)
print("SAMPLE ADDRESS DATA FROM STAGING:")
print("="*60)
cur.execute("""
    SELECT employee_name, street1, city, postal_code, main_phone
    FROM staging_employee_reference_data
    WHERE street1 IS NOT NULL
    ORDER BY employee_name
    LIMIT 5
""")

for row in cur.fetchall():
    print(f"\n{row[0]}:")
    print(f"  {row[1]}")
    print(f"  {row[2]}, {row[3] or ''}")
    print(f"  Phone: {row[4] or 'N/A'}")

cur.close()
conn.close()
