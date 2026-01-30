#!/usr/bin/env python3
"""
Simple bulk insert of all batch_deposit_allocations to charter_payments.
No deduplication - will get unique constraint errors for true duplicates.
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
    password=os.getenv("DB_PASSWORD", "***REMOVED***"),
    cursor_factory=RealDictCursor
)

cur = conn.cursor()

print("="*100)
print("BULK MIGRATE ALL BATCH_DEPOSIT_ALLOCATIONS")
print("="*100)
print(f"\nMode: {'DRY RUN' if DRY_RUN else 'WRITE MODE'}")
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

cur.execute("SELECT COUNT(*) as count FROM batch_deposit_allocations")
total_bda = cur.fetchone()['count']
print(f"Total batch_deposit_allocations to migrate: {total_bda:,}")

if not DRY_RUN:
    # Truncate charter_payments to start fresh
    print("\nClearing charter_payments of batch_deposit_allocation entries...")
    cur.execute("DELETE FROM charter_payments WHERE source = 'batch_deposit_allocation' OR source = 'charter_refund'")
    deleted = cur.rowcount
    print(f"  Deleted {deleted:,} entries")
    
    # Now insert ALL batch_deposit_allocations
    print("\nInserting all batch_deposit_allocations...")
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
    
    bda_inserted = cur.rowcount
    print(f"  Inserted {bda_inserted:,} batch_deposit_allocation payments")
    
    # Insert refunds
    print("\nInserting all charter_refunds...")
    cur.execute("""
        INSERT INTO charter_payments (charter_id, client_name, charter_date, payment_date, amount, payment_method, source, payment_key, imported_at)
        SELECT 
            cr.reserve_number,
            c.client_display_name,
            c.charter_date,
            cr.refund_date,
            -cr.amount,
            COALESCE(cr.payment_method, 'unknown'),
            'charter_refund',
            'REFUND_' || cr.id,
            NOW()
        FROM charter_refunds cr
        JOIN charters c ON c.reserve_number = cr.reserve_number
    """)
    
    refund_inserted = cur.rowcount
    print(f"  Inserted {refund_inserted:,} charter_refund payments")
    
    conn.commit()

# Verify
cur.execute("SELECT COUNT(*) as count FROM charter_payments WHERE source = 'batch_deposit_allocation'")
final_bda = cur.fetchone()['count']
print(f"\nFinal charter_payments (batch_deposit_allocation source): {final_bda:,}")

cur.execute("SELECT COUNT(*) as count FROM charter_payments")
total_payments = cur.fetchone()['count']
print(f"Total charter_payments: {total_payments:,}")

print("\n" + "="*100)
if DRY_RUN:
    print("DRY RUN - NO CHANGES")
else:
    print("✅ MIGRATION COMPLETE")

cur.close()
conn.close()

print("="*100)
