#!/usr/bin/env python3
"""Check which split/parent columns exist in receipts table."""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 80)
print("RECEIPTS TABLE - SPLIT/PARENT SCHEMA")
print("=" * 80)

# Check for split-related columns
cur.execute("""
    SELECT column_name, data_type, character_maximum_length, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'receipts'
    AND (
        column_name LIKE '%split%' 
        OR column_name LIKE '%parent%'
        OR column_name LIKE '%personal%'
        OR column_name = 'business_personal'
    )
    ORDER BY ordinal_position
""")

columns = cur.fetchall()

if columns:
    print(f"\nFound {len(columns)} split/parent-related columns:\n")
    for col_name, data_type, max_length, nullable in columns:
        type_info = data_type
        if max_length:
            type_info += f"({max_length})"
        null_info = "NULL" if nullable == "YES" else "NOT NULL"
        print(f"  {col_name:30} {type_info:20} {null_info}")
else:
    print("\n⚠️  NO split/parent columns found in receipts table")

# Check if receipt_splits table exists
print("\n" + "=" * 80)
print("RECEIPT_SPLITS TABLE")
print("=" * 80)

cur.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'receipt_splits'
    )
""")
table_exists = cur.fetchone()[0]

if table_exists:
    print("\n✅ receipt_splits table EXISTS")
    
    # Get row count
    cur.execute("SELECT COUNT(*) FROM receipt_splits")
    count = cur.fetchone()[0]
    print(f"   Records: {count:,}")
    
    # Get schema
    cur.execute("""
        SELECT column_name, data_type, character_maximum_length, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'receipt_splits'
        ORDER BY ordinal_position
    """)
    split_cols = cur.fetchall()
    print("\n   Columns:")
    for col_name, data_type, max_length, nullable in split_cols:
        type_info = data_type
        if max_length:
            type_info += f"({max_length})"
        null_info = "NULL" if nullable == "YES" else "NOT NULL"
        print(f"     {col_name:30} {type_info:20} {null_info}")
else:
    print("\n❌ receipt_splits table DOES NOT EXIST")
    print("   Migration file exists but not applied")

# Check sample 2019 split receipts
print("\n" + "=" * 80)
print("2019 SPLIT RECEIPTS - SCHEMA USAGE")
print("=" * 80)

cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        description,
        parent_receipt_id,
        split_key,
        split_group_total,
        is_split_receipt,
        is_personal_purchase,
        owner_personal_amount,
        business_personal
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
    AND description ILIKE '%split%'
    LIMIT 5
""")

splits = cur.fetchall()
if splits:
    print(f"\nFirst 5 split receipts from 2019:\n")
    for row in splits:
        (receipt_id, receipt_date, vendor, amount, desc, parent_id, 
         split_key, split_total, is_split, is_personal, personal_amt, biz_personal) = row
        
        print(f"Receipt {receipt_id} | {receipt_date} | {vendor} | ${amount}")
        print(f"  Description: {desc}")
        print(f"  parent_receipt_id: {parent_id}")
        print(f"  split_key: {split_key}")
        print(f"  split_group_total: {split_total}")
        print(f"  is_split_receipt: {is_split}")
        print(f"  is_personal_purchase: {is_personal}")
        print(f"  owner_personal_amount: {personal_amt}")
        print(f"  business_personal: {biz_personal}")
        print()

cur.close()
conn.close()

print("=" * 80)
print("✅ Schema check complete")
print("=" * 80)
