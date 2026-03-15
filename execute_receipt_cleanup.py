#!/usr/bin/env python3
"""Execute the receipt duplicate cleanup SQL script"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

password = os.getenv('LOCAL_DB_PASSWORD') or os.getenv('DB_PASSWORD') or os.getenv('POSTGRES_PASSWORD')

conn = psycopg2.connect(
    host='localhost',
    database=os.getenv('LOCAL_DB_NAME') or 'almsdata',
    user=os.getenv('LOCAL_DB_USER') or 'postgres',
    password=password
)

cur = conn.cursor()

print("=" * 120)
print("EXECUTING RECEIPT DUPLICATE CLEANUP")
print("=" * 120)

# Count before
cur.execute("SELECT COUNT(*) FROM receipts")
before_count = cur.fetchone()[0]
print(f"\nReceipts before cleanup: {before_count:,}")

cur.execute("SELECT COUNT(*) FROM receipts WHERE gross_amount = 0 AND banking_transaction_id IS NOT NULL")
zero_amount_linked = cur.fetchone()[0]
print(f"Zero-amount receipts linked to banking: {zero_amount_linked:,}")

# Read and execute the SQL script
print(f"\n📄 Reading cleanup script: cleanup_receipt_duplicates_20260214_082902.sql")

with open('l:\\limo\\cleanup_receipt_duplicates_20260214_082902.sql', 'r') as f:
    sql_script = f.read()

print(f"✅ Script loaded ({len(sql_script)} characters)")

# Execute the script
print(f"\n⏳ Executing cleanup script...")
try:
    cur.execute(sql_script)
    print(f"✅ Cleanup executed successfully")
except Exception as e:
    print(f"❌ Error executing cleanup: {e}")
    conn.rollback()
    conn.close()
    exit(1)

# Count after
cur.execute("SELECT COUNT(*) FROM receipts")
after_count = cur.fetchone()[0]
deleted_count = before_count - after_count

print(f"\n📊 RESULTS:")
print(f"  Receipts before: {before_count:,}")
print(f"  Receipts after:  {after_count:,}")
print(f"  Deleted:         {deleted_count:,}")

# Verify backup table was created
cur.execute("""
    SELECT COUNT(*) 
    FROM pg_tables 
    WHERE tablename = 'receipts_backup_20260214082902'
""")
backup_exists = cur.fetchone()[0]

if backup_exists:
    cur.execute("SELECT COUNT(*) FROM receipts_backup_20260214082902")
    backup_count = cur.fetchone()[0]
    print(f"\n✅ Backup table created: receipts_backup_20260214082902")
    print(f"   Backup contains: {backup_count:,} receipts")
else:
    print(f"\n⚠️  Warning: Backup table not found!")

# Verify zero-amount receipts are gone
cur.execute("SELECT COUNT(*) FROM receipts WHERE gross_amount = 0 AND banking_transaction_id IS NOT NULL")
remaining_zero = cur.fetchone()[0]
print(f"\n✅ Zero-amount receipts linked to banking after cleanup: {remaining_zero:,}")

if remaining_zero == 0:
    print(f"   Perfect! All zero-amount duplicates removed.")
else:
    print(f"   ⚠️  Warning: Still have {remaining_zero:,} zero-amount receipts")

# Show breakdown of what was deleted
cur.execute("""
    SELECT 
        SUBSTRING(vendor_name, 1, 40) as vendor,
        COUNT(*) as count
    FROM receipts_backup_20260214082902
    GROUP BY SUBSTRING(vendor_name, 1, 40)
    ORDER BY COUNT(*) DESC
    LIMIT 10
""")

print(f"\n📋 Top 10 vendors in deleted receipts:")
for row in cur.fetchall():
    vendor, count = row
    print(f"  {vendor[:40]:<40}: {count:>4,} receipts")

conn.close()

print("\n" + "=" * 120)
print("✅ CLEANUP COMPLETE!")
print("=" * 120)
print(f"\n✨ Successfully removed {deleted_count:,} duplicate receipts")
print(f"💾 Backup saved in: receipts_backup_20260214082902")
print()
