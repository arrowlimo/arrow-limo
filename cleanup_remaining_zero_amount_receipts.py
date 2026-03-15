#!/usr/bin/env python3
"""Clean up remaining zero-amount duplicate receipts (second pass)"""
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
print("SECOND PASS: CLEANING REMAINING ZERO-AMOUNT DUPLICATES")
print("=" * 120)

# Check what's remaining
cur.execute("""
    SELECT COUNT(*) 
    FROM receipts 
    WHERE gross_amount = 0 
      AND banking_transaction_id IS NOT NULL
""")
remaining_zero = cur.fetchone()[0]

print(f"\n📊 Remaining zero-amount receipts linked to banking: {remaining_zero:,}")

if remaining_zero == 0:
    print(f"\n✅ No more duplicates to clean!")
    conn.close()
    exit(0)

# Analyze what these are
print(f"\n🔍 Analyzing remaining duplicates...")
cur.execute("""
    SELECT 
        SUBSTRING(r.vendor_name, 1, 40) as vendor,
        r.category,
        r.created_from_banking,
        COUNT(*) as count
    FROM receipts r
    WHERE r.gross_amount = 0 
      AND r.banking_transaction_id IS NOT NULL
    GROUP BY SUBSTRING(r.vendor_name, 1, 40), r.category, r.created_from_banking
    ORDER BY COUNT(*) DESC
    LIMIT 20
""")

print(f"\nTop remaining duplicates:")
for row in cur.fetchall():
    vendor, category, created_from_banking, count = row
    flag = "✓" if created_from_banking else "✗"
    print(f"  {vendor[:40]:<40} | Cat: {(category or 'NULL'):<20} | FromBanking:{flag} | Count: {count:>3}")

# Auto-confirm deletion (user requested cleanup)
print(f"\n" + "=" * 120)
print(f"PROCEEDING WITH CLEANUP (Auto-confirmed)")
print(f"These are ALL zero-amount receipts that duplicate banking_transactions.")
print(f"=" * 120)

# Execute cleanup
print(f"\n⏳ Step 1: Creating backup table for second pass...")
cur.execute("""
    CREATE TABLE receipts_backup_20260214082902_pass2 AS
    SELECT * FROM receipts
    WHERE gross_amount = 0 
      AND banking_transaction_id IS NOT NULL
""")

cur.execute("SELECT COUNT(*) FROM receipts_backup_20260214082902_pass2")
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
    )
""")
fk_updated = cur.rowcount
print(f"✅ Cleared {fk_updated:,} foreign key references")

print(f"\n⏳ Step 3: Deleting remaining duplicate receipts...")
cur.execute("""
    DELETE FROM receipts
    WHERE gross_amount = 0 
      AND banking_transaction_id IS NOT NULL
""")
deleted_count = cur.rowcount
print(f"✅ Deleted {deleted_count:,} receipts")

# Verify
cur.execute("SELECT COUNT(*) FROM receipts WHERE gross_amount = 0 AND banking_transaction_id IS NOT NULL")
final_remaining = cur.fetchone()[0]

print(f"\n📊 FINAL VERIFICATION:")
print(f"  Deleted in pass 2: {deleted_count:,}")
print(f"  Remaining zero-amount duplicates: {final_remaining:,}")

if final_remaining == 0:
    print(f"\n✅ Perfect! All zero-amount duplicates removed!")
else:
    print(f"\n⚠️  Warning: Still {final_remaining:,} zero-amount duplicates remaining")

# Commit
print(f"\n💾 Committing changes...")
conn.commit()
print(f"✅ Changes committed successfully!")

conn.close()

print("\n" + "=" * 120)
print("✅ SECOND PASS COMPLETE!")
print("=" * 120)
