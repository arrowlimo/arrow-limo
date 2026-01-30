#!/usr/bin/env python
"""Inspect receipts table schema and data state."""
import psycopg2
from psycopg2.extras import RealDictCursor
import os

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password=os.environ.get('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Get receipts table schema
cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'receipts'
    ORDER BY ordinal_position
""")

print('=== RECEIPTS TABLE SCHEMA ===\n')
columns = cur.fetchall()
for col in columns:
    nullable = "YES" if col['is_nullable'] == 'YES' else "NO"
    default = col['column_default'] if col['column_default'] else "-"
    print(f"{col['column_name']:35} | {col['data_type']:20} | NULL: {nullable:3} | default: {default}")

# Get count summary
cur.execute('SELECT COUNT(*) FROM receipts')
total_receipts = cur.fetchone()['count']

print(f'\n=== SUMMARY ===')
print(f'Total receipts: {total_receipts:,}')
print(f'Total columns: {len(columns)}')

# Check for actual data in key columns
print('\n=== DATA PRESENCE CHECK ===')
cur.execute("""
    SELECT 
        COUNT(DISTINCT vendor_name) as unique_vendors,
        COUNT(CASE WHEN business_personal IS NOT NULL THEN 1 END) as with_business_personal,
        COUNT(CASE WHEN gl_account_code IS NOT NULL THEN 1 END) as with_gl_code,
        COUNT(CASE WHEN gst_code IS NOT NULL THEN 1 END) as with_gst_code,
        COUNT(CASE WHEN vehicle_id IS NOT NULL THEN 1 END) as with_vehicle,
        COUNT(CASE WHEN is_split_receipt = TRUE THEN 1 END) as split_receipts,
        COUNT(CASE WHEN is_personal_purchase = TRUE THEN 1 END) as personal_purchases,
        COUNT(CASE WHEN is_driver_reimbursement = TRUE THEN 1 END) as driver_reimbursements,
        COUNT(CASE WHEN tip > 0 THEN 1 END) as with_tips,
        COUNT(CASE WHEN card_number IS NOT NULL THEN 1 END) as with_card_number
    FROM receipts
""")

data = cur.fetchone()
for key, value in data.items():
    print(f'{key:30}: {value:,}')

# Sample of existing data
print('\n=== SAMPLE RECORDS WITH CATEGORY DATA ===')
cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        gst_amount,
        business_personal,
        gl_account_code,
        gl_account_name,
        is_split_receipt,
        is_personal_purchase,
        vehicle_id,
        card_number
    FROM receipts
    WHERE business_personal IS NOT NULL OR gl_account_code IS NOT NULL
    LIMIT 15
""")

for row in cur.fetchall():
    print(f"\nID: {row['receipt_id']} | {row['receipt_date']}")
    print(f"  Vendor: {row['vendor_name']}")
    print(f"  Amount: ${row['gross_amount']} (GST: ${row['gst_amount']})")
    print(f"  Category: {row['business_personal']} → {row['gl_account_code']} ({row['gl_account_name']})")
    if row['is_split_receipt']:
        print(f"  ⚠️  SPLIT RECEIPT")
    if row['is_personal_purchase']:
        print(f"  🏠 PERSONAL PURCHASE")
    if row['vehicle_id']:
        print(f"  🚗 Vehicle: {row['vehicle_id']}")
    if row['card_number']:
        print(f"  💳 Card: ...{row['card_number'][-4:] if len(row['card_number']) >= 4 else row['card_number']}")

conn.close()
print("\n=== SCHEMA INSPECTION COMPLETE ===")
