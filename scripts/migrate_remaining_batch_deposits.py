#!/usr/bin/env python3
"""
Migrate ALL remaining batch_deposit_allocations to charter_payments.
The consolidation script only migrated 988 due to duplicate checking.
This script will migrate all 4,744 remaining allocations.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
import sys
from datetime import datetime

load_dotenv()

DRY_RUN = '--dry-run' in sys.argv

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    database=os.getenv("DB_NAME", "almsdata"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "***REDACTED***"),
    cursor_factory=RealDictCursor
)

cur = conn.cursor()

print("="*100)
print("MIGRATE ALL REMAINING BATCH_DEPOSIT_ALLOCATIONS")
print("="*100)
print(f"\nMode: {'DRY RUN' if DRY_RUN else 'WRITE MODE'}")
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# Check current state
cur.execute("""
    SELECT COUNT(*) as count 
    FROM batch_deposit_allocations bda
    WHERE NOT EXISTS (
        SELECT 1 FROM charter_payments cp
        WHERE cp.charter_id = bda.reserve_number
          AND cp.payment_key = 'BDA_' || bda.allocation_id
    )
""")
unmigrated = cur.fetchone()['count']

print(f"Unmigrated batch_deposit_allocations: {unmigrated:,} rows\n")

if unmigrated == 0:
    print("✅ All batch_deposit_allocations already migrated")
    cur.close()
    conn.close()
    sys.exit(0)

print("✅ Migrating all remaining batch_deposit_allocations...")

if not DRY_RUN:
    # Insert ALL batch_deposit_allocations (may have duplicates in charter_payments already)
    # Using WHERE NOT EXISTS to avoid duplicates
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
    conn.commit()
    print(f"   ✅ Inserted {inserted:,} batch_deposit_allocation payments")
    
    # Verify
    cur.execute("""
        SELECT COUNT(*) as count 
        FROM charter_payments
        WHERE source = 'batch_deposit_allocation'
    """)
    total_bda = cur.fetchone()['count']
    print(f"   ✅ Total batch_deposit_allocation payments now: {total_bda:,}")
else:
    print(f"   DRY RUN: Would insert {unmigrated:,} payments")

print("\n" + "="*100)
print("MIGRATION COMPLETE")
print("="*100)

cur.close()
conn.close()
