#!/usr/bin/env python3
"""Check which receipt system tables exist."""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

conn = get_db_connection()
cur = conn.cursor()

tables_to_check = [
    'receipt_line_items',
    'vendor_default_categories', 
    'cash_box_transactions',
    'driver_floats',
    'receipt_categories'
]

print("Checking receipt system tables...")
print("="*80)

existing = []
missing = []

for table in tables_to_check:
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        )
    """, (table,))
    
    if cur.fetchone()[0]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        existing.append((table, count))
    else:
        missing.append(table)

print(f"\nExisting tables: {len(existing)}")
for table, count in existing:
    print(f"  ✓ {table}: {count} rows")

print(f"\nMissing tables: {len(missing)}")
for table in missing:
    print(f"  ✗ {table}")

# Check receipts table features
print("\nReceipts table features:")
print("-"*80)

cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN vehicle_id IS NOT NULL THEN 1 END) as with_vehicle,
        COUNT(CASE WHEN split_key IS NOT NULL THEN 1 END) as with_split_key,
        COUNT(CASE WHEN fuel_amount > 0 THEN 1 END) as with_fuel_amount,
        COUNT(CASE WHEN business_personal = 'personal' THEN 1 END) as personal
    FROM receipts
""")

row = cur.fetchone()
print(f"  Total receipts: {row[0]}")
print(f"  With vehicle_id: {row[1]} ({row[1]*100//row[0] if row[0] else 0}%)")
print(f"  With split_key: {row[2]} ({row[2]*100//row[0] if row[0] else 0}%)")
print(f"  With fuel_amount: {row[3]} ({row[3]*100//row[0] if row[0] else 0}%)")
print(f"  Personal receipts: {row[4]} ({row[4]*100//row[0] if row[0] else 0}%)")

conn.close()
