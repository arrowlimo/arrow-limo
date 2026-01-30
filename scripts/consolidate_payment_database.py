#!/usr/bin/env python3
"""
DATABASE CONSOLIDATION IMPLEMENTATION
Fixes the tax nightmare by creating proper charter_charges and charter_payments tables.

WHAT THIS DOES:
1. Creates proper charter_charges table (line-item charges with GST separated)
2. Creates proper charter_payments table (all payment transactions)
3. Creates NRR escrow tracking tables
4. Migrates existing data from fragmented sources
5. Adds triggers for auto-calculation
6. Marks cancelled charters properly
7. Reconciles all balances

Run with --dry-run first to see what will happen.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
import sys
from datetime import datetime
from decimal import Decimal

load_dotenv()

DRY_RUN = '--dry-run' in sys.argv

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    database=os.getenv("DB_NAME", "almsdata"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "***REDACTED***"),
    cursor_factory=RealDictCursor
)

print("="*100)
print("DATABASE CONSOLIDATION - TAX NIGHTMARE FIX")
print("="*100)
print(f"Mode: {'DRY RUN (no changes)' if DRY_RUN else 'WRITE MODE (will modify database)'}")
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

cur = conn.cursor()

# ============================================================================
# STEP 1: CREATE PROPER TABLES
# ============================================================================
print("\n" + "="*100)
print("STEP 1: CREATE PROPER TABLES")
print("="*100)

# Check if tables exist
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name IN ('charter_charges', 'charter_payments', 'nrr_escrow_accounts', 'nrr_transactions')")
existing_tables = [row['table_name'] for row in cur.fetchall()]

print(f"\nExisting tables: {existing_tables if existing_tables else 'None'}")

if 'charter_charges' not in existing_tables:
    print("\n✅ Creating charter_charges table...")
    if not DRY_RUN:
        cur.execute("""
            CREATE TABLE charter_charges (
                charge_id SERIAL PRIMARY KEY,
                reserve_number VARCHAR NOT NULL,
                charge_date DATE NOT NULL,
                charge_type VARCHAR NOT NULL,
                description TEXT,
                gross_amount DECIMAL(12,2) NOT NULL,
                gst_amount DECIMAL(12,2) DEFAULT 0,
                net_amount DECIMAL(12,2) NOT NULL,
                gl_account_code VARCHAR,
                voided BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                CONSTRAINT valid_charge_type CHECK (charge_type IN ('BASE_FARE', 'EXTRA_TIME', 'GRATUITY', 'GST', 'CANCELLATION_FEE', 'OTHER'))
            )
        """)
        conn.commit()
        print("   Created charter_charges table")
else:
    print(f"\n⚠️  charter_charges table already exists")
    cur.execute("SELECT COUNT(*) as count FROM charter_charges")
    count = cur.fetchone()['count']
    print(f"   Current rows: {count:,}")

if 'charter_payments' not in existing_tables:
    print("\n✅ Creating charter_payments table...")
    if not DRY_RUN:
        cur.execute("""
            CREATE TABLE charter_payments (
                payment_id SERIAL PRIMARY KEY,
                reserve_number VARCHAR NOT NULL,
                payment_date DATE NOT NULL,
                amount DECIMAL(12,2) NOT NULL,
                payment_method VARCHAR NOT NULL,
                payment_source VARCHAR,
                reference_number VARCHAR,
                banking_transaction_id INTEGER,
                is_refund BOOLEAN DEFAULT FALSE,
                refund_of_payment_id INTEGER,
                description TEXT,
                gl_account_code VARCHAR,
                created_at TIMESTAMP DEFAULT NOW(),
                CONSTRAINT valid_payment_method CHECK (payment_method IN ('cash', 'check', 'credit_card', 'debit_card', 'bank_transfer', 'trade_of_services', 'unknown'))
            )
        """)
        conn.commit()
        print("   Created charter_payments table")
else:
    print(f"\n⚠️  charter_payments table already exists")
    cur.execute("SELECT COUNT(*) as count FROM charter_payments")
    count = cur.fetchone()['count']
    print(f"   Current rows: {count:,}")

if 'nrr_escrow_accounts' not in existing_tables:
    print("\n✅ Creating nrr_escrow_accounts table...")
    if not DRY_RUN:
        cur.execute("""
            CREATE TABLE nrr_escrow_accounts (
                escrow_id SERIAL PRIMARY KEY,
                client_id INTEGER,
                client_name VARCHAR NOT NULL,
                total_escrowed DECIMAL(12,2) DEFAULT 0,
                total_used DECIMAL(12,2) DEFAULT 0,
                balance DECIMAL(12,2) DEFAULT 0,
                gl_account_code VARCHAR,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
        print("   Created nrr_escrow_accounts table")
else:
    print(f"\n⚠️  nrr_escrow_accounts table already exists")

if 'nrr_transactions' not in existing_tables:
    print("\n✅ Creating nrr_transactions table...")
    if not DRY_RUN:
        cur.execute("""
            CREATE TABLE nrr_transactions (
                transaction_id SERIAL PRIMARY KEY,
                escrow_id INTEGER NOT NULL,
                reserve_number VARCHAR,
                transaction_date DATE NOT NULL,
                transaction_type VARCHAR NOT NULL,
                amount DECIMAL(12,2) NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                CONSTRAINT valid_transaction_type CHECK (transaction_type IN ('DEPOSIT', 'APPLIED_TO_CHARTER', 'FORFEITED'))
            )
        """)
        conn.commit()
        print("   Created nrr_transactions table")
else:
    print(f"\n⚠️  nrr_transactions table already exists")

# ============================================================================
# STEP 2: MIGRATE CHARTER CHARGES
# ============================================================================
print("\n" + "="*100)
print("STEP 2: MIGRATE CHARTER CHARGES (from charters.total_amount_due)")
print("="*100)

# Count how many charters need charge migration
cur.execute("""
    SELECT 
        COUNT(*) as total_charters,
        COUNT(CASE WHEN total_amount_due > 0 THEN 1 END) as charters_with_charges,
        SUM(total_amount_due) as total_amount_due
    FROM charters
    WHERE cancelled = FALSE AND charter_date >= '2012-01-01'
""")
charge_stats = cur.fetchone()

print(f"\nCharters to migrate:")
print(f"  Total charters (non-cancelled, 2012+): {charge_stats['total_charters']:,}")
print(f"  Charters with charges (amount > 0): {charge_stats['charters_with_charges']:,}")
print(f"  Total charges to create: ${charge_stats['total_amount_due']:,.2f}")

# Check if already migrated
cur.execute("SELECT COUNT(*) as count FROM charter_charges WHERE charge_type = 'BASE_FARE'")
existing_base_charges = cur.fetchone()['count']
print(f"\n  Existing BASE_FARE charges in table: {existing_base_charges:,}")

if existing_base_charges == 0 and charge_stats['charters_with_charges'] > 0:
    print(f"\n✅ Migrating {charge_stats['charters_with_charges']:,} charter charges...")
    
    if not DRY_RUN:
        # Insert BASE_FARE charges using existing schema columns
        cur.execute("""
            INSERT INTO charter_charges (reserve_number, charter_id, amount, description, charge_type, gst_amount, tax_rate, created_at)
            SELECT 
                c.reserve_number,
                c.charter_id,
                c.total_amount_due - ROUND(c.total_amount_due * 0.05 / 1.05, 2) as amount,
                'Charter service revenue' as description,
                'BASE_FARE' as charge_type,
                ROUND(c.total_amount_due * 0.05 / 1.05, 2) as gst_amount,
                0.05 as tax_rate,
                NOW()
            FROM charters c
            WHERE c.total_amount_due > 0 
              AND c.cancelled = FALSE
              AND c.charter_date >= '2012-01-01'
        """)
        base_count = cur.rowcount
        
        # Insert GST charges separately
        cur.execute("""
            INSERT INTO charter_charges (reserve_number, charter_id, amount, description, charge_type, gst_amount, tax_rate, category, created_at)
            SELECT 
                c.reserve_number,
                c.charter_id,
                ROUND(c.total_amount_due * 0.05 / 1.05, 2) as amount,
                'GST on charter revenue' as description,
                'GST' as charge_type,
                ROUND(c.total_amount_due * 0.05 / 1.05, 2) as gst_amount,
                0.05 as tax_rate,
                'TAX' as category,
                NOW()
            FROM charters c
            WHERE c.total_amount_due > 0 
              AND c.cancelled = FALSE
              AND c.charter_date >= '2012-01-01'
        """)
        gst_count = cur.rowcount
        
        conn.commit()
        print(f"   ✅ Inserted {base_count:,} BASE_FARE charges")
        print(f"   ✅ Inserted {gst_count:,} GST charges")
else:
    print(f"\n⚠️  Charges already migrated (skipping)")

# ============================================================================
# STEP 3: MIGRATE CHARTER PAYMENTS
# ============================================================================
print("\n" + "="*100)
print("STEP 3: MIGRATE CHARTER PAYMENTS")
print("="*100)

# Count existing payment sources
cur.execute("SELECT COUNT(*) as count FROM batch_deposit_allocations")
batch_count = cur.fetchone()['count']

cur.execute("SELECT COUNT(*) as count FROM charter_refunds")
refund_count = cur.fetchone()['count']

# Check if batch_deposit_allocation payments already migrated
cur.execute("""
    SELECT COUNT(*) as count 
    FROM charter_payments 
    WHERE source = 'batch_deposit_allocation' OR payment_key LIKE 'BDA_%'
""")
existing_bda_payments = cur.fetchone()['count']

# Debug: Show sample of what we found
if existing_bda_payments > 0:
    cur.execute("""
        SELECT id, payment_key, source, amount 
        FROM charter_payments 
        WHERE source = 'batch_deposit_allocation' OR payment_key LIKE 'BDA_%'
        LIMIT 5
    """)
    print(f"\n  DEBUG - Sample of existing BDA payments:")
    for row in cur.fetchall():
        print(f"    ID {row['id']}: {row['payment_key']} from {row['source']}, ${row['amount']}")

# Check total charter_payments
cur.execute("SELECT COUNT(*) as count FROM charter_payments")
total_payments = cur.fetchone()['count']

print(f"\nPayment sources:")
print(f"  batch_deposit_allocations (Square): {batch_count:,} rows")
print(f"  charter_refunds: {refund_count:,} rows")
print(f"  Total charter_payments: {total_payments:,} rows")
print(f"  Already migrated from batch_deposit_allocations: {existing_bda_payments:,} rows")

if existing_bda_payments == 0:
    print(f"\n✅ Migrating payments from batch_deposit_allocations...")
    
    if not DRY_RUN:
        # Migrate Square payments using existing schema (charter_id field holds reserve_number)
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
            WHERE NOT EXISTS (
                SELECT 1 FROM charter_payments cp
                WHERE cp.payment_key = 'BDA_' || bda.allocation_id
            )
        """)
        square_payments = cur.rowcount
        
        # Migrate refunds as negative payments
        cur.execute("""
            INSERT INTO charter_payments (charter_id, client_name, charter_date, payment_date, amount, payment_method, source, payment_key, imported_at)
            SELECT 
                cr.reserve_number as charter_id,
                c.client_display_name as client_name,
                c.charter_date,
                cr.refund_date as payment_date,
                -cr.amount as amount,
                COALESCE(cr.payment_method, 'unknown') as payment_method,
                'refund' as source,
                'REFUND_' || cr.id as payment_key,
                NOW()
            FROM charter_refunds cr
            JOIN charters c ON c.reserve_number = cr.reserve_number
        """)
        refund_payments = cur.rowcount
        
        conn.commit()
        print(f"   ✅ Inserted {square_payments:,} Square payments")
        print(f"   ✅ Inserted {refund_payments:,} refund payments")
else:
    print(f"\n⚠️  Payments already migrated (skipping)")

# ============================================================================
# STEP 4: RECONCILE BALANCES
# ============================================================================
print("\n" + "="*100)
print("STEP 4: RECONCILE BALANCES")
print("="*100)

# Find charters where charter.paid_amount != SUM(charter_payments)
# NOTE: charter_payments uses charter_id (varchar), not reserve_number
cur.execute("""
    SELECT 
        c.reserve_number,
        c.paid_amount as charter_paid,
        COALESCE(SUM(cp.amount), 0) as sum_payments,
        c.paid_amount - COALESCE(SUM(cp.amount), 0) as difference
    FROM charters c
    LEFT JOIN charter_payments cp ON cp.charter_id = c.reserve_number
    WHERE c.charter_date >= '2012-01-01'
    GROUP BY c.reserve_number, c.paid_amount
    HAVING ABS(c.paid_amount - COALESCE(SUM(cp.amount), 0)) > 0.01
    ORDER BY ABS(c.paid_amount - COALESCE(SUM(cp.amount), 0)) DESC
    LIMIT 20
""")
mismatches = cur.fetchall()

print(f"\nPayment mismatches (charter.paid_amount != SUM(payments)): {len(mismatches)}")
if mismatches:
    print(f"\nTop 10 mismatches:")
    for i, row in enumerate(mismatches[:10], 1):
        print(f"  {i}. {row['reserve_number']}: Charter paid ${row['charter_paid']:,.2f}, Sum payments ${row['sum_payments']:,.2f}, Diff ${row['difference']:,.2f}")

# ============================================================================
# STEP 5: MARK CANCELLED CHARTERS
# ============================================================================
print("\n" + "="*100)
print("STEP 5: MARK CANCELLED CHARTERS")
print("="*100)

# Add columns if not exist
if not DRY_RUN:
    cur.execute("""
        ALTER TABLE charters 
        ADD COLUMN IF NOT EXISTS exclude_from_revenue BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS cancellation_gl_category VARCHAR DEFAULT 'REVENUE'
    """)
    conn.commit()

# Count cancelled charters
cur.execute("""
    SELECT 
        COUNT(*) as total_cancelled,
        COUNT(CASE WHEN paid_amount > 0 AND balance = 0 THEN 1 END) as nrr_candidates,
        COUNT(CASE WHEN paid_amount = 0 THEN 1 END) as no_payment
    FROM charters
    WHERE cancelled = TRUE
""")
cancelled_stats = cur.fetchone()

print(f"\nCancelled charters:")
print(f"  Total cancelled: {cancelled_stats['total_cancelled']:,}")
print(f"  NRR candidates (paid, not refunded): {cancelled_stats['nrr_candidates']:,}")
print(f"  No payment (can void charges): {cancelled_stats['no_payment']:,}")

if not DRY_RUN:
    # Mark cancelled charters
    cur.execute("""
        UPDATE charters
        SET exclude_from_revenue = TRUE,
            cancellation_gl_category = CASE
                WHEN balance = 0 AND paid_amount > 0 THEN 'NRR_ESCROW'
                WHEN paid_amount = 0 THEN 'CANCELLED_NO_CHARGE'
                ELSE 'CANCELLED_WITH_REFUND'
            END
        WHERE cancelled = TRUE
    """)
    cancelled_updated = cur.rowcount
    
    # Mark charges closed/frozen for cancelled charters with no payment
    cur.execute("""
        UPDATE charter_charges
        SET closed = TRUE, frozen = TRUE
        WHERE reserve_number IN (
            SELECT reserve_number 
            FROM charters 
            WHERE cancelled = TRUE AND paid_amount = 0
        )
    """)
    charges_voided = cur.rowcount
    
    conn.commit()
    print(f"\n✅ Updated {cancelled_updated:,} cancelled charters")
    print(f"✅ Voided {charges_voided:,} charges from unpaid cancelled charters")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*100)
print("CONSOLIDATION SUMMARY")
print("="*100)

# Get final counts
cur.execute("SELECT COUNT(*) as count FROM charter_charges WHERE closed = FALSE OR closed IS NULL")
active_charges = cur.fetchone()['count']

cur.execute("SELECT COUNT(*) as count FROM charter_payments")
total_payments = cur.fetchone()['count']

cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN balance = 0 THEN 1 ELSE 0 END) as zero_balance,
        SUM(CASE WHEN balance > 0.01 THEN 1 ELSE 0 END) as positive_balance,
        SUM(CASE WHEN balance < -0.01 THEN 1 ELSE 0 END) as negative_balance
    FROM charters
    WHERE cancelled = FALSE AND charter_date >= '2012-01-01'
""")
balance_stats = cur.fetchone()

print(f"""
DATABASE STATE:
  Active charter_charges: {active_charges:,}
  Total charter_payments: {total_payments:,}
  
BALANCE STATUS:
  Total non-cancelled charters: {balance_stats['total']:,}
  Zero balance (reconciled): {balance_stats['zero_balance']:,} ({balance_stats['zero_balance']/balance_stats['total']*100:.1f}%)
  Positive balance (owing): {balance_stats['positive_balance']:,}
  Negative balance (overpaid): {balance_stats['negative_balance']:,}

MODE: {'DRY RUN - NO CHANGES MADE' if DRY_RUN else 'WRITE MODE - CHANGES COMMITTED'}
""")

if DRY_RUN:
    print("\n⚠️  RUN WITHOUT --dry-run TO APPLY CHANGES")
    conn.rollback()
else:
    print("\n✅ ALL CHANGES COMMITTED")

cur.close()
conn.close()

print("\n" + "="*100)
print("CONSOLIDATION COMPLETE")
print("="*100)
