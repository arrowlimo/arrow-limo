#!/usr/bin/env python3
"""
Mark all linked records as reconciled and verified:
1. Banking transactions with links -> reconciled=TRUE, verified=TRUE
2. Manually created receipts (not created_from_banking) -> is_verified_banking=TRUE
3. All charter payments -> mark as verified (via payment notes or status)
"""
import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    
    print("\n" + "="*80)
    print("MARK ALL RECONCILED & VERIFIED - PRODUCTION RUN")
    print("="*80 + "\n")
    
    # ========================================================================
    # STEP 1: Mark Banking Transactions as Reconciled & Verified
    # ========================================================================
    print("1️⃣ BANKING TRANSACTIONS - Mark Reconciled & Verified:")
    print("-" * 80)
    
    cur = conn.cursor()
    
    # Mark all with payment or receipt links as reconciled and verified
    cur.execute("""
        UPDATE banking_transactions
        SET 
            reconciliation_status = 'reconciled',
            verified = TRUE,
            reconciled_at = CURRENT_TIMESTAMP,
            reconciled_by = 'AUTO_SYSTEM'
        WHERE (reconciled_payment_id IS NOT NULL OR reconciled_receipt_id IS NOT NULL)
        AND (verified IS NULL OR verified = FALSE OR reconciliation_status != 'reconciled')
    """)
    
    banking_count = cur.rowcount
    conn.commit()
    print(f"   ✅ Marked {banking_count:,} banking transactions as reconciled & verified")
    
    # ========================================================================
    # STEP 2: Mark Manual Receipts as Verified
    # ========================================================================
    print("\n2️⃣ MANUAL RECEIPTS - Mark Verified:")
    print("-" * 80)
    
    # Mark receipts that were manually saved (not auto-created from banking)
    cur.execute("""
        UPDATE receipts
        SET 
            is_verified_banking = TRUE,
            verified_at = CURRENT_TIMESTAMP,
            verified_by_user = 'AUTO_SYSTEM',
            verified_source = 'Manual entry - auto-verified'
        WHERE created_from_banking = FALSE
        AND (is_verified_banking IS NULL OR is_verified_banking = FALSE)
    """)
    
    manual_receipts = cur.rowcount
    conn.commit()
    print(f"   ✅ Marked {manual_receipts:,} manually-created receipts as verified")
    
    # ========================================================================
    # STEP 3: Mark Auto-Created Receipts as Verified
    # ========================================================================
    print("\n3️⃣ AUTO-CREATED RECEIPTS - Mark Verified:")
    print("-" * 80)
    
    # Mark receipts that were auto-created from banking
    cur.execute("""
        UPDATE receipts
        SET 
            is_verified_banking = TRUE,
            verified_at = CURRENT_TIMESTAMP,
            verified_source = 'Auto-created from banking reconciliation'
        WHERE created_from_banking = TRUE
        AND (is_verified_banking IS NULL OR is_verified_banking = FALSE)
    """)
    
    auto_receipts = cur.rowcount
    conn.commit()
    print(f"   ✅ Marked {auto_receipts:,} auto-created receipts as verified")
    
    # ========================================================================
    # STEP 4: Verify Charter Payments Status
    # ========================================================================
    print("\n4️⃣ CHARTER PAYMENTS - Status Check:")
    print("-" * 80)
    
    # Check payment status distribution for charter payments
    cur.execute("""
        SELECT 
            p.status,
            COUNT(*) as count,
            SUM(p.amount) as total_amount
        FROM payments p
        WHERE p.reserve_number ~ '^[0-9]{6}$'  -- Charter reserve numbers are 6 digits
        GROUP BY p.status
        ORDER BY count DESC
    """)
    
    print("   Payment Status Distribution (Charter Payments):")
    for status, count, total in cur.fetchall():
        print(f"      {status:20s}: {count:6,} payments | ${total:,.2f}")
    
    # Check if payments table has a verified column
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'payments' AND column_name = 'verified'
    """)
    
    has_verified = cur.fetchone()
    if has_verified:
        print("\n   Found 'verified' column in payments - updating...")
        cur.execute("""
            UPDATE payments
            SET verified = TRUE
            WHERE reserve_number ~ '^[0-9]{6}$'
            AND (verified IS NULL OR verified = FALSE)
        """)
        charter_payments = cur.rowcount
        conn.commit()
        print(f"   ✅ Marked {charter_payments:,} charter payments as verified")
    else:
        print("   ℹ️  No 'verified' column in payments table - using status field only")
    
    # ========================================================================
    # STEP 5: Verification Summary
    # ========================================================================
    print("\n5️⃣ VERIFICATION SUMMARY:")
    print("-" * 80)
    
    # Banking reconciliation status
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN verified = TRUE THEN 1 END) as verified,
            COUNT(CASE WHEN reconciliation_status = 'reconciled' THEN 1 END) as reconciled,
            COUNT(CASE WHEN reconciled_payment_id IS NOT NULL THEN 1 END) as has_payment_link,
            COUNT(CASE WHEN reconciled_receipt_id IS NOT NULL THEN 1 END) as has_receipt_link
        FROM banking_transactions
    """)
    
    row = cur.fetchone()
    print(f"\n   📊 Banking Transactions:")
    print(f"      Total:           {row[0]:8,}")
    print(f"      Verified:        {row[1]:8,} ({row[1]*100.0/row[0]:.1f}%)")
    print(f"      Reconciled:      {row[2]:8,} ({row[2]*100.0/row[0]:.1f}%)")
    print(f"      Payment Links:   {row[3]:8,}")
    print(f"      Receipt Links:   {row[4]:8,}")
    
    # Receipts verification status
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN is_verified_banking = TRUE THEN 1 END) as verified,
            COUNT(CASE WHEN created_from_banking = TRUE THEN 1 END) as auto_created,
            COUNT(CASE WHEN created_from_banking = FALSE THEN 1 END) as manual,
            COUNT(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 END) as has_banking_link
        FROM receipts
    """)
    
    row = cur.fetchone()
    print(f"\n   📊 Receipts:")
    print(f"      Total:           {row[0]:8,}")
    print(f"      Verified:        {row[1]:8,} ({row[1]*100.0/row[0]:.1f}%)")
    print(f"      Auto-Created:    {row[2]:8,}")
    print(f"      Manual:          {row[3]:8,}")
    print(f"      Banking Links:   {row[4]:8,}")
    
    # Payments status
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN reserve_number ~ '^[0-9]{6}$' THEN 1 END) as charter_payments,
            COUNT(CASE WHEN status = 'paid' THEN 1 END) as paid_status
        FROM payments
    """)
    
    row = cur.fetchone()
    print(f"\n   📊 Payments:")
    print(f"      Total:           {row[0]:8,}")
    print(f"      Charter:         {row[1]:8,}")
    print(f"      Status='paid':   {row[2]:8,}")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)
    print("✅ RECONCILIATION & VERIFICATION COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
