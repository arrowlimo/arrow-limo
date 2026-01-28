#!/usr/bin/env python3
"""
LMS Database Verification
Compare PostgreSQL payment matching against original LMS data
"""

import sys
import os
sys.path.insert(0, os.getcwd())

from api import get_db_connection
import pyodbc

def connect_to_lms():
    """Connect to the LMS Access database"""
    try:
        LMS_PATH = r'L:\limo\lms.mdb'
        conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
        return pyodbc.connect(conn_str)
    except Exception as e:
        print(f"❌ Could not connect to LMS: {e}")
        return None

def verify_lms_payment_matching():
    """Verify payment matching against LMS source data"""
    
    print("🔍 VERIFYING PAYMENT MATCHING AGAINST LMS DATABASE...")
    
    lms_conn = connect_to_lms()
    if not lms_conn:
        print("❌ Cannot verify - LMS database not accessible")
        return
    
    pg_conn = get_db_connection()
    
    try:
        lms_cur = lms_conn.cursor()
        pg_cur = pg_conn.cursor()
        
        # Get LMS payment statistics
        print("\n📊 LMS DATABASE ANALYSIS:")
        
        # Total payments in LMS
        lms_cur.execute("SELECT COUNT(*) FROM Payment")
        lms_total_payments = lms_cur.fetchone()[0]
        print(f"   LMS total payments: {lms_total_payments:,}")
        
        # LMS payments with Reserve_No (should be matched)
        lms_cur.execute("SELECT COUNT(*) FROM Payment WHERE Reserve_No IS NOT NULL AND Reserve_No <> ''")
        lms_payments_with_reserve = lms_cur.fetchone()[0]
        print(f"   LMS payments with Reserve_No: {lms_payments_with_reserve:,}")
        
        # LMS payment amount totals
        lms_cur.execute("SELECT SUM(Amount) FROM Payment WHERE Amount IS NOT NULL")
        lms_total_amount = lms_cur.fetchone()[0] or 0
        print(f"   LMS total payment amount: ${lms_total_amount:,.2f}")
        
        # Get PostgreSQL statistics
        print("\n📊 POSTGRESQL DATABASE ANALYSIS:")
        
        pg_cur.execute("SELECT COUNT(*) FROM payments")
        pg_total_payments = pg_cur.fetchone()[0]
        print(f"   PostgreSQL total payments: {pg_total_payments:,}")
        
        pg_cur.execute("SELECT COUNT(*) FROM payments WHERE reserve_number IS NOT NULL")
        pg_matched_payments = pg_cur.fetchone()[0]
        print(f"   PostgreSQL matched payments: {pg_matched_payments:,}")
        
        pg_cur.execute("SELECT SUM(amount) FROM payments WHERE amount IS NOT NULL")
        pg_total_amount = pg_cur.fetchone()[0] or 0
        print(f"   PostgreSQL total amount: ${pg_total_amount:,.2f}")
        
        # Compare matching rates
        print(f"\n🔍 COMPARISON ANALYSIS:")
        if lms_payments_with_reserve > 0:
            lms_expected_match_rate = (lms_payments_with_reserve / lms_total_payments * 100)
            print(f"   LMS expected match rate: {lms_expected_match_rate:.1f}% ({lms_payments_with_reserve:,}/{lms_total_payments:,})")
        
        pg_actual_match_rate = (pg_matched_payments / pg_total_payments * 100) if pg_total_payments > 0 else 0
        print(f"   PostgreSQL actual match rate: {pg_actual_match_rate:.1f}% ({pg_matched_payments:,}/{pg_total_payments:,})")
        
        # Sample LMS payments that should be matched
        print(f"\n📋 SAMPLE LMS PAYMENTS WITH RESERVE NUMBERS:")
        lms_cur.execute("""
            SELECT TOP 10 PaymentID, Reserve_No, Account_No, Amount, [Key], LastUpdated
            FROM Payment 
            WHERE Reserve_No IS NOT NULL AND Reserve_No <> ''
            ORDER BY LastUpdated DESC
        """)
        
        lms_samples = lms_cur.fetchall()
        for payment_id, reserve_no, account_no, amount, key, last_updated in lms_samples:
            print(f"   LMS Payment {payment_id}: Reserve {reserve_no} | Account {account_no} | ${amount:,.2f}")
            
            # Check if this exists and is matched in PostgreSQL
            pg_cur.execute("""
                SELECT payment_id, charter_id, amount, reserve_number
                FROM payments 
                WHERE reserve_number = %s OR payment_key = %s
                LIMIT 1
            """, (reserve_no, key))
            
            pg_match = pg_cur.fetchone()
            if pg_match:
                pg_payment_id, charter_id, pg_amount, pg_reserve = pg_match
                match_status = "✅ MATCHED" if charter_id else "❌ UNMATCHED"
                print(f"     → PostgreSQL: Payment {pg_payment_id} | {match_status} | ${pg_amount:,.2f}")
            else:
                print(f"     → PostgreSQL: ❌ NOT FOUND")
        
        # Check for payments that exist in PostgreSQL but not LMS
        print(f"\n🔍 CHECKING FOR POSTGRESQL-ONLY PAYMENTS:")
        pg_cur.execute("""
            SELECT COUNT(*) 
            FROM payments 
            WHERE payment_key NOT LIKE 'LMS%' 
            OR payment_key IS NULL
        """)
        non_lms_payments = pg_cur.fetchone()[0]
        print(f"   Non-LMS payments in PostgreSQL: {non_lms_payments:,}")
        
        # Sample recent unmatched payments
        print(f"\n📋 RECENT UNMATCHED PAYMENTS IN POSTGRESQL:")
        pg_cur.execute("""
            SELECT payment_id, payment_date, amount, reserve_number, payment_key, notes
            FROM payments 
            WHERE reserve_number IS NULL
            AND payment_date >= '2024-01-01'
            ORDER BY payment_date DESC
            LIMIT 10
        """)
        
        recent_unmatched = pg_cur.fetchall()
        for payment_id, payment_date, amount, reserve_no, payment_key, notes in recent_unmatched:
            reserve_str = reserve_no or "None"
            key_str = payment_key or "None"
            notes_str = (notes[:50] + "...") if notes and len(notes) > 50 else (notes or "")
            print(f"   Payment {payment_id}: {payment_date} | ${amount:,.2f} | Reserve: {reserve_str}")
            print(f"     Key: {key_str} | Notes: {notes_str}")
            
            # Check if this reserve number exists in LMS
            if reserve_no:
                try:
                    lms_cur.execute("SELECT COUNT(*) FROM Reserve WHERE Reserve_No = ?", (reserve_no,))
                    lms_charter_exists = lms_cur.fetchone()[0] > 0
                    charter_status = "✅ EXISTS" if lms_charter_exists else "❌ NOT FOUND"
                    print(f"     LMS Charter: {charter_status}")
                except:
                    print(f"     LMS Charter: ❓ CHECK FAILED")
        
        return {
            'lms_total': lms_total_payments,
            'lms_with_reserve': lms_payments_with_reserve,
            'pg_total': pg_total_payments,
            'pg_matched': pg_matched_payments,
            'lms_amount': lms_total_amount,
            'pg_amount': pg_total_amount
        }
        
    finally:
        lms_cur.close()
        lms_conn.close()
        pg_cur.close()
        pg_conn.close()

def check_missing_lms_data():
    """Check for specific LMS data that might be missing"""
    
    print("\n🔍 CHECKING FOR MISSING LMS DATA PATTERNS...")
    
    lms_conn = connect_to_lms()
    if not lms_conn:
        return
    
    pg_conn = get_db_connection()
    
    try:
        lms_cur = lms_conn.cursor()
        pg_cur = pg_conn.cursor()
        
        # Check LMS payment methods
        print("\n📊 LMS PAYMENT METHODS:")
        lms_cur.execute("""
            SELECT Pymt_Type, COUNT(*) as count, SUM(Amount) as total
            FROM Payment 
            WHERE Pymt_Type IS NOT NULL
            GROUP BY Pymt_Type
            ORDER BY COUNT(*) DESC
        """)
        
        lms_payment_methods = lms_cur.fetchall()
        for method, count, total in lms_payment_methods:
            total_str = f"${total:,.2f}" if total else "$0.00"
            print(f"   {method}: {count:,} payments ({total_str})")
        
        # Check if all these made it to PostgreSQL
        print("\n📊 POSTGRESQL PAYMENT METHODS:")
        pg_cur.execute("""
            SELECT payment_method, COUNT(*) as count, SUM(amount) as total
            FROM payments 
            WHERE payment_method IS NOT NULL
            GROUP BY payment_method
            ORDER BY COUNT(*) DESC
        """)
        
        pg_payment_methods = pg_cur.fetchall()
        for method, count, total in pg_payment_methods:
            total_str = f"${total:,.2f}" if total else "$0.00"
            print(f"   {method}: {count:,} payments ({total_str})")
        
        # Check for LMS deposits that might not be properly linked
        print("\n🔍 CHECKING LMS DEPOSITS:")
        lms_cur.execute("""
            SELECT COUNT(*) 
            FROM Deposit 
            WHERE [Type] = 'R'
        """)
        lms_deposit_receipts = lms_cur.fetchone()[0]
        print(f"   LMS deposit receipts: {lms_deposit_receipts:,}")
        
        pg_cur.execute("""
            SELECT COUNT(*) 
            FROM payments 
            WHERE notes LIKE '%LMS Deposit%'
        """)
        pg_lms_deposits = pg_cur.fetchone()[0]
        print(f"   PostgreSQL LMS deposit references: {pg_lms_deposits:,}")
        
        if lms_deposit_receipts != pg_lms_deposits:
            print(f"   ⚠️  MISMATCH: LMS has {lms_deposit_receipts:,} but PostgreSQL has {pg_lms_deposits:,}")
        
    finally:
        lms_cur.close()
        lms_conn.close()
        pg_cur.close()
        pg_conn.close()

if __name__ == "__main__":
    print("🔍 LMS DATABASE VERIFICATION")
    print("=" * 60)
    
    # Verify payment matching against LMS
    stats = verify_lms_payment_matching()
    
    # Check for missing data patterns
    check_missing_lms_data()
    
    print(f"\n" + "=" * 60)
    print("🔍 LMS VERIFICATION COMPLETE")
    if stats:
        lms_expected = (stats['lms_with_reserve'] / stats['lms_total'] * 100) if stats['lms_total'] > 0 else 0
        pg_actual = (stats['pg_matched'] / stats['pg_total'] * 100) if stats['pg_total'] > 0 else 0
        print(f"Expected match rate from LMS: {lms_expected:.1f}%")
        print(f"Actual match rate in PostgreSQL: {pg_actual:.1f}%")
        if pg_actual < lms_expected:
            print("❌ We're missing matches that should exist based on LMS data")
        else:
            print("✅ Match rate meets or exceeds LMS expectations")
    print("=" * 60)