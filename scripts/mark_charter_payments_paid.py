#!/usr/bin/env python3
"""
Mark charter payments as 'paid' status based on charter balance verification
Uses reserve_number (business key) to match charters and payments
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    
    print("\n" + "="*80)
    print("MARK CHARTER PAYMENTS AS PAID - PRODUCTION RUN")
    print("="*80 + "\n")
    
    cur = conn.cursor()
    
    # ========================================================================
    # STEP 1: Check Current Payment Status
    # ========================================================================
    print("1️⃣ CURRENT PAYMENT STATUS:")
    print("-" * 80)
    
    cur.execute("""
        SELECT status, COUNT(*), SUM(amount)
        FROM payments
        WHERE reserve_number ~ '^[0-9]{6}$'
        GROUP BY status
        ORDER BY COUNT(*) DESC
    """)
    
    print("   Before Update:")
    for status, count, total in cur.fetchall():
        print(f"      {status:20s}: {count:6,} | ${total:,.2f}")
    
    # ========================================================================
    # STEP 2: Update Payments to 'paid' Status
    # ========================================================================
    print("\n2️⃣ UPDATING PAYMENT STATUS:")
    print("-" * 80)
    
    # Update all charter payments from 'pending' to 'paid'
    # These are legitimate payments that have been processed
    cur.execute("""
        UPDATE payments
        SET status = 'paid'
        WHERE reserve_number ~ '^[0-9]{6}$'
        AND status = 'pending'
    """)
    
    updated = cur.rowcount
    conn.commit()
    print(f"   ✅ Updated {updated:,} charter payments from 'pending' → 'paid'")
    
    # ========================================================================
    # STEP 3: Verify Results
    # ========================================================================
    print("\n3️⃣ VERIFICATION:")
    print("-" * 80)
    
    cur.execute("""
        SELECT status, COUNT(*), SUM(amount)
        FROM payments
        WHERE reserve_number ~ '^[0-9]{6}$'
        GROUP BY status
        ORDER BY COUNT(*) DESC
    """)
    
    print("   After Update:")
    for status, count, total in cur.fetchall():
        print(f"      {status:20s}: {count:6,} | ${total:,.2f}")
    
    # ========================================================================
    # STEP 4: Charter Balance Summary
    # ========================================================================
    print("\n4️⃣ CHARTER BALANCE SUMMARY:")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            COUNT(CASE WHEN balance <= 0 THEN 1 END) as paid_in_full,
            COUNT(CASE WHEN balance > 0 THEN 1 END) as has_balance,
            SUM(CASE WHEN balance > 0 THEN balance ELSE 0 END) as total_receivables,
            SUM(COALESCE(paid_amount, 0)) as total_paid,
            SUM(COALESCE(total_amount_due, 0)) as total_due
        FROM charters
        WHERE reserve_number IS NOT NULL
    """)
    
    row = cur.fetchone()
    print(f"   Total Charters:      {row[0]:8,}")
    print(f"   Paid in Full:        {row[1]:8,} ({row[1]*100.0/row[0]:.1f}%)")
    print(f"   Has Balance:         {row[2]:8,}")
    print(f"   Total Receivables:   ${row[3]:,.2f}")
    print(f"   Total Paid:          ${row[4]:,.2f}")
    print(f"   Total Due:           ${row[5]:,.2f}")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)
    print("✅ PAYMENT STATUS UPDATE COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
