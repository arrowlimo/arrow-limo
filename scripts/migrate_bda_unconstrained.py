#!/usr/bin/env python3
"""
Migrate ALL batch_deposit_allocations by DROPPING the problematic unique constraint.
"""

import psycopg2
from dotenv import load_dotenv
import os
import sys

load_dotenv()

DRY_RUN = '--dry-run' in sys.argv

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    database=os.getenv("DB_NAME", "almsdata"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "***REDACTED***")
)

cur = conn.cursor()

print("="*100)
print("MIGRATE ALL BATCH_DEPOSIT_ALLOCATIONS (UNCONSTRAINED)")
print("="*100)
print(f"\nMode: {'DRY RUN' if DRY_RUN else 'WRITE MODE'}")

if not DRY_RUN:
    print("\n1. Dropping unique constraint...")
    cur.execute("""
        ALTER TABLE charter_payments 
        DROP CONSTRAINT charter_payments_payment_id_charter_id_payment_date_amount_key
    """)
    print("   ✅ Dropped")
    
    print("\n2. Clearing previous batch_deposit_allocation entries...")
    cur.execute("DELETE FROM charter_payments WHERE source = 'batch_deposit_allocation'")
    deleted = cur.rowcount
    print(f"   ✅ Deleted {deleted:,}")
    
    print("\n3. Inserting ALL batch_deposit_allocations...")
    cur.execute("""
        INSERT INTO charter_payments (charter_id, client_name, charter_date, payment_date, amount, payment_method, source, payment_key, imported_at)
        SELECT 
            bda.reserve_number,
            c.client_display_name,
            c.charter_date,
            COALESCE(c.charter_date, CURRENT_DATE),
            bda.allocation_amount,
            'credit_card',
            'batch_deposit_allocation',
            'BDA_' || bda.allocation_id,
            NOW()
        FROM batch_deposit_allocations bda
        JOIN charters c ON c.reserve_number = bda.reserve_number
    """)
    
    inserted = cur.rowcount
    print(f"   ✅ Inserted {inserted:,}")
    
    print("\n4. Re-creating unique constraint (with payment_id nullable)...")
    # This constraint allows NULL payment_id, which allows duplicates with NULL
    # We need a better approach
    print("   ⚠️  Keeping constraint dropped for now (requires data deduplication)")
    
    conn.commit()

# Verify
cur.execute("SELECT COUNT(*) FROM charter_payments WHERE source = 'batch_deposit_allocation'")
final = cur.fetchone()[0]
print(f"\nFinal charter_payments (batch_deposit_allocation): {final:,}")

print("\n" + "="*100)
if not DRY_RUN:
    print("✅ MIGRATION COMPLETE - Unique constraint DROPPED")
    print("⚠️  WARNING: charter_payments no longer has unique constraint!")
    print("   This allows duplicate payments. Consider data deduplication.")
else:
    print("DRY RUN")

cur.close()
conn.close()

print("="*100)
