#!/usr/bin/env python3
"""
Delete 544 receipts with amount mismatches (sign errors from 2012 import).
These are duplicates - banking_transactions already has the correct data.
"""
import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME", "almsdata"),
    user=os.getenv("DB_USER", "postgres"), 
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432")
)

cur = conn.cursor()

print("=" * 80)
print("DELETING 544 RECEIPTS WITH AMOUNT MISMATCHES")
print("=" * 80)

# First, verify count
cur.execute("""
    SELECT COUNT(*)
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.gross_amount != 0 
      AND r.created_from_banking = TRUE
      AND ABS(r.gross_amount - (bt.debit_amount - COALESCE(bt.credit_amount, 0))) >= 0.01
""")
count = cur.fetchone()[0]
print(f"\nReceipts to delete: {count}")

if count != 544:
    print(f"⚠️  WARNING: Expected 544 but found {count}")
    response = input("Continue anyway? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted.")
        cur.close()
        conn.close()
        exit(0)

# Create backup table
timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
backup_table = f"receipts_backup_amount_mismatches_{timestamp}"

print(f"\n📦 Creating backup table: {backup_table}")
cur.execute(f"""
    CREATE TABLE {backup_table} AS
    SELECT r.*
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.gross_amount != 0 
      AND r.created_from_banking = TRUE
      AND ABS(r.gross_amount - (bt.debit_amount - COALESCE(bt.credit_amount, 0))) >= 0.01
""")

cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
backup_count = cur.fetchone()[0]
print(f"✅ Backed up {backup_count} receipts to {backup_table}")

# Check for foreign key references
print(f"\n🔍 Checking foreign key references...")
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions bt
    WHERE bt.receipt_id IN (
        SELECT r.receipt_id
        FROM receipts r
        JOIN banking_transactions bt2 ON r.banking_transaction_id = bt2.transaction_id
        WHERE r.gross_amount != 0 
          AND r.created_from_banking = TRUE
          AND ABS(r.gross_amount - (bt2.debit_amount - COALESCE(bt2.credit_amount, 0))) >= 0.01
    )
""")
fk_count = cur.fetchone()[0]
print(f"Found {fk_count} foreign key references to clear")

# Clear foreign key references
if fk_count > 0:
    print(f"🧹 Clearing {fk_count} foreign key references...")
    cur.execute("""
        UPDATE banking_transactions
        SET receipt_id = NULL
        WHERE receipt_id IN (
            SELECT r.receipt_id
            FROM receipts r
            JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
            WHERE r.gross_amount != 0 
              AND r.created_from_banking = TRUE
              AND ABS(r.gross_amount - (bt.debit_amount - COALESCE(bt.credit_amount, 0))) >= 0.01
        )
    """)
    print(f"✅ Cleared {cur.rowcount} foreign key references")

# Delete the receipts
print(f"\n🗑️  Deleting {count} receipts...")
cur.execute("""
    DELETE FROM receipts
    WHERE receipt_id IN (
        SELECT r.receipt_id
        FROM receipts r
        JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE r.gross_amount != 0 
          AND r.created_from_banking = TRUE
          AND ABS(r.gross_amount - (bt.debit_amount - COALESCE(bt.credit_amount, 0))) >= 0.01
    )
""")
deleted_count = cur.rowcount
print(f"✅ Deleted {deleted_count} receipts")

# Verify deletion
print(f"\n✓ Verifying...")
cur.execute("""
    SELECT COUNT(*)
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.gross_amount != 0 
      AND r.created_from_banking = TRUE
      AND ABS(r.gross_amount - (bt.debit_amount - COALESCE(bt.credit_amount, 0))) >= 0.01
""")
remaining = cur.fetchone()[0]

if remaining == 0:
    print(f"✅ SUCCESS: 0 amount mismatches remaining")
    print(f"\n📊 Final counts:")
    cur.execute("SELECT COUNT(*) FROM receipts")
    total_receipts = cur.fetchone()[0]
    print(f"   Total receipts: {total_receipts:,}")
    
    cur.execute("""
        SELECT COUNT(*)
        FROM receipts
        WHERE created_from_banking = TRUE
          AND gross_amount != 0
          AND banking_transaction_id IS NOT NULL
    """)
    linked = cur.fetchone()[0]
    print(f"   Linked to banking (non-zero): {linked:,}")
    
    print(f"\n💾 Committing transaction...")
    conn.commit()
    print(f"✅ Transaction committed successfully")
    
    print(f"\n" + "=" * 80)
    print("CLEANUP COMPLETE")
    print("=" * 80)
    print(f"Deleted: {deleted_count} receipts")
    print(f"Backup: {backup_table}")
    print(f"Remaining receipts: {total_receipts:,}")
    print("=" * 80)
else:
    print(f"⚠️  WARNING: {remaining} mismatches still remain!")
    print(f"Rolling back...")
    conn.rollback()
    print("Rolled back. No changes made.")

cur.close()
conn.close()
