#!/usr/bin/env python3
"""Execute the receipt duplicate cleanup with FK fix"""
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

conn.autocommit = False
cur = conn.cursor()

print("=" * 120)
print("EXECUTING RECEIPT DUPLICATE CLEANUP (WITH FK FIX)")
print("=" * 120)

# Count before
cur.execute("SELECT COUNT(*) FROM receipts")
before_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM receipts WHERE gross_amount = 0 AND banking_transaction_id IS NOT NULL")
zero_amount_linked = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions bt
    WHERE bt.receipt_id IN (
        SELECT receipt_id 
        FROM receipts 
        WHERE gross_amount = 0 
          AND banking_transaction_id IS NOT NULL
    )
""")
fk_references = cur.fetchone()[0]

print(f"\n📊 BEFORE CLEANUP:")
print(f"  Total receipts: {before_count:,}")
print(f"  Zero-amount duplicates: {zero_amount_linked:,}")
print(f"  Banking FK references to clean: {fk_references:,}")

# Execute cleanup
print(f"\n⏳ Step 1: Creating backup table...")
cur.execute("""
    CREATE TABLE receipts_backup_20260214082902 AS
    SELECT * FROM receipts
    WHERE gross_amount = 0 
      AND banking_transaction_id IS NOT NULL
      AND created_from_banking = TRUE
""")

cur.execute("SELECT COUNT(*) FROM receipts_backup_20260214082902")
backup_count = cur.fetchone()[0]
print(f"✅ Backed up {backup_count:,} receipts")

print(f"\n⏳ Step 2: Removing foreign key references from banking_transactions...")
cur.execute("""
    UPDATE banking_transactions
    SET receipt_id = NULL
    WHERE receipt_id IN (
        SELECT receipt_id 
        FROM receipts 
        WHERE gross_amount = 0 
          AND banking_transaction_id IS NOT NULL
          AND created_from_banking = TRUE
    )
""")
fk_updated = cur.rowcount
print(f"✅ Cleared {fk_updated:,} foreign key references")

print(f"\n⏳ Step 3: Deleting duplicate receipts...")
cur.execute("""
    DELETE FROM receipts
    WHERE gross_amount = 0 
      AND banking_transaction_id IS NOT NULL
      AND created_from_banking = TRUE
""")
deleted_count = cur.rowcount
print(f"✅ Deleted {deleted_count:,} receipts")

# Verify
cur.execute("SELECT COUNT(*) FROM receipts")
after_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM receipts WHERE gross_amount = 0 AND banking_transaction_id IS NOT NULL")
remaining_zero = cur.fetchone()[0]

print(f"\n📊 AFTER CLEANUP:")
print(f"  Total receipts: {after_count:,}")
print(f"  Deleted: {deleted_count:,}")
print(f"  Remaining zero-amount: {remaining_zero:,}")

# Show what was deleted
cur.execute("""
    SELECT 
        SUBSTRING(vendor_name, 1, 40) as vendor,
        COUNT(*) as count,
        category
    FROM receipts_backup_20260214082902
    GROUP BY SUBSTRING(vendor_name, 1, 40), category
    ORDER BY COUNT(*) DESC
    LIMIT 15
""")

print(f"\n📋 Top deleted receipts by vendor:")
for row in cur.fetchall():
    vendor, count, category = row
    print(f"  {vendor[:40]:<40}: {count:>4,} receipts | Category: {category or 'NULL'}")

# Commit
print(f"\n💾 Committing changes...")
conn.commit()
print(f"✅ Changes committed successfully!")

conn.close()

print("\n" + "=" * 120)
print("✅ CLEANUP COMPLETE!")
print("=" * 120)
print(f"\n✨ Successfully removed {deleted_count:,} duplicate receipts")
print(f"💾 Backup saved in: receipts_backup_20260214082902")
print(f"🔗 Cleared {fk_updated:,} foreign key references from banking_transactions")
print()
