#!/usr/bin/env python3
"""
DATABASE CONSOLIDATION v2 - SIMPLE AND DIRECT
Consolidates payment and charge data without complex deduplication.
Assumes starting fresh from the actual database state.

WHAT THIS DOES:
1. Populate charter_charges with BASE_FARE and GST (846 charters)
2. Populate charter_payments from batch_deposit_allocations (5,732 payments)
3. Populate charter_payments from charter_refunds (343 refunds)
4. Mark cancelled charters
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
print("DATABASE CONSOLIDATION v2 - SIMPLE MIGRATION")
print("="*100)
print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE MODE'}")
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# ============================================================================
# STEP 1: CLEAR EXISTING CONSOLIDATION DATA
# ============================================================================
print("\nSTEP 1: CHECKING EXISTING DATA")
print("-"*100)

if not DRY_RUN:
    # Delete charges we created (tag='consolidation_import')
    cur.execute("DELETE FROM charter_charges WHERE tag = 'consolidation_import'")
    deleted_charges = cur.rowcount
    print(f"Deleted {deleted_charges:,} consolidation_import charges")
    
    # Delete payments from batch_deposit_allocation
    cur.execute("DELETE FROM charter_payments WHERE source = 'batch_deposit_allocation'")
    deleted_bda = cur.rowcount
    print(f"Deleted {deleted_bda:,} batch_deposit_allocation payments")
    
    # Delete payments from refund source
    cur.execute("DELETE FROM charter_payments WHERE source = 'charter_refund'")
    deleted_refunds = cur.rowcount
    print(f"Deleted {deleted_refunds:,} charter_refund payments")
    
    conn.commit()

# ============================================================================
# STEP 2: MIGRATE CHARTER CHARGES
# ============================================================================
print("\nSTEP 2: MIGRATE CHARTER CHARGES")
print("-"*100)

cur.execute("""
    SELECT COUNT(*) as count
    FROM charters
    WHERE total_amount_due > 0 
      AND cancelled = FALSE
      AND charter_date >= '2012-01-01'
""")
charge_count = cur.fetchone()['count']
print(f"Charters with charges: {charge_count:,}")

if not DRY_RUN:
    # Insert BASE_FARE charges
    cur.execute("""
        INSERT INTO charter_charges (reserve_number, charter_id, amount, description, charge_type, gst_amount, tax_rate, created_at, tag)
        SELECT 
            c.reserve_number,
            c.charter_id,
            c.total_amount_due - ROUND(c.total_amount_due * 0.05 / 1.05, 2) as amount,
            'Charter service revenue' as description,
            'BASE_FARE' as charge_type,
            ROUND(c.total_amount_due * 0.05 / 1.05, 2) as gst_amount,
            0.05 as tax_rate,
            NOW(),
            'consolidation_import' as tag
        FROM charters c
        WHERE c.total_amount_due > 0 
          AND c.cancelled = FALSE
          AND c.charter_date >= '2012-01-01'
    """)
    base_count = cur.rowcount
    print(f"✅ Inserted {base_count:,} BASE_FARE charges")
    
    # Insert GST charges
    cur.execute("""
        INSERT INTO charter_charges (reserve_number, charter_id, amount, description, charge_type, gst_amount, tax_rate, category, created_at, tag)
        SELECT 
            c.reserve_number,
            c.charter_id,
            ROUND(c.total_amount_due * 0.05 / 1.05, 2) as amount,
            'GST on charter revenue' as description,
            'GST' as charge_type,
            ROUND(c.total_amount_due * 0.05 / 1.05, 2) as gst_amount,
            0.05 as tax_rate,
            'TAX' as category,
            NOW(),
            'consolidation_import' as tag
        FROM charters c
        WHERE c.total_amount_due > 0 
          AND c.cancelled = FALSE
          AND c.charter_date >= '2012-01-01'
    """)
    gst_count = cur.rowcount
    print(f"✅ Inserted {gst_count:,} GST charges")
    
    conn.commit()

# ============================================================================
# STEP 3: MIGRATE CHARTER PAYMENTS
# ============================================================================
print("\nSTEP 3: MIGRATE CHARTER PAYMENTS")
print("-"*100)

cur.execute("SELECT COUNT(*) as count FROM batch_deposit_allocations")
bda_count = cur.fetchone()['count']
cur.execute("SELECT COUNT(*) as count FROM charter_refunds")
refund_count = cur.fetchone()['count']
print(f"batch_deposit_allocations: {bda_count:,} rows")
print(f"charter_refunds: {refund_count:,} rows")

if not DRY_RUN:
    # Insert batch_deposit_allocation payments
    cur.execute("""
        INSERT INTO charter_payments (charter_id, client_name, charter_date, payment_date, amount, payment_method, source, payment_key, imported_at)
        SELECT 
            bda.reserve_number as charter_id,
            c.client_display_name as client_name,
            c.charter_date,
            COALESCE(c.charter_date, CURRENT_DATE) as payment_date,
            bda.allocation_amount as amount,
            'credit_card' as payment_method,
            'batch_deposit_allocation' as source,
            'BDA_' || bda.allocation_id as payment_key,
            NOW()
        FROM batch_deposit_allocations bda
        JOIN charters c ON c.reserve_number = bda.reserve_number
    """)
    bda_inserted = cur.rowcount
    print(f"✅ Inserted {bda_inserted:,} batch_deposit_allocation payments")
    
    # Insert refund payments
    cur.execute("""
        INSERT INTO charter_payments (charter_id, client_name, charter_date, payment_date, amount, payment_method, source, payment_key, imported_at)
        SELECT 
            cr.reserve_number as charter_id,
            c.client_display_name as client_name,
            c.charter_date,
            cr.refund_date as payment_date,
            -cr.amount as amount,
            COALESCE(cr.payment_method, 'unknown') as payment_method,
            'charter_refund' as source,
            'REFUND_' || cr.id as payment_key,
            NOW()
        FROM charter_refunds cr
        JOIN charters c ON c.reserve_number = cr.reserve_number
    """)
    refund_inserted = cur.rowcount
    print(f"✅ Inserted {refund_inserted:,} charter_refund payments")
    
    conn.commit()

# ============================================================================
# STEP 4: VERIFY FINAL STATE
# ============================================================================
print("\nSTEP 4: VERIFY FINAL STATE")
print("-"*100)

cur.execute("SELECT COUNT(*) as count FROM charter_charges WHERE tag = 'consolidation_import'")
final_charges = cur.fetchone()['count']
print(f"Consolidation charter_charges: {final_charges:,}")

cur.execute("SELECT COUNT(*) as count FROM charter_payments WHERE source = 'batch_deposit_allocation'")
final_bda = cur.fetchone()['count']
print(f"Batch_deposit_allocation payments: {final_bda:,}")

cur.execute("SELECT COUNT(*) as count FROM charter_payments WHERE source = 'charter_refund'")
final_refunds = cur.fetchone()['count']
print(f"Charter_refund payments: {final_refunds:,}")

print("\n" + "="*100)
if DRY_RUN:
    print("DRY RUN - NO CHANGES MADE. Run without --dry-run to apply.")
    conn.rollback()
else:
    print("✅ ALL CHANGES COMMITTED")

cur.close()
conn.close()

print("="*100)
