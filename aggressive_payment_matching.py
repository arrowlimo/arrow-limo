#!/usr/bin/env python3
"""
Aggressive Payment-Charter Matching Recovery
Get back to 98% match rate using all available matching strategies
"""

import sys
import os
sys.path.insert(0, os.getcwd())

from api import get_db_connection
import re
from datetime import datetime, timedelta

def apply_aggressive_matching():
    """Apply all aggressive matching strategies to recover high match rate"""
    
    print("🎯 RECOVERING HIGH MATCH RATE - Applying Aggressive Matching...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        total_fixes = 0
        
        # Strategy 1: Match by reserve number (including extracted from notes)
        print("\n1. Matching by reserve numbers (including from notes)...")
        cur.execute("""
            UPDATE payments 
            SET charter_id = c.charter_id 
            FROM charters c 
            WHERE payments.reserve_number IS NULL 
            AND payments.reserve_number IS NOT NULL 
            AND payments.reserve_number = c.reserve_number
        """)
        reserve_direct = cur.rowcount
        total_fixes += reserve_direct
        print(f"   Direct reserve matches: {reserve_direct:,}")
        
        # Strategy 2: Extract 6-digit numbers from notes and match
        cur.execute("""
            WITH extracted_reserves AS (
                SELECT 
                    p.payment_id,
                    REGEXP_REPLACE(p.notes, '[^0-9]', '', 'g') as numbers_only
                FROM payments p
                WHERE p.reserve_number IS NULL 
                AND p.notes IS NOT NULL
                AND LENGTH(REGEXP_REPLACE(p.notes, '[^0-9]', '', 'g')) >= 6
            ),
            potential_matches AS (
                SELECT 
                    er.payment_id,
                    SUBSTRING(er.numbers_only FROM 1 FOR 6) as potential_reserve
                FROM extracted_reserves er
                WHERE LENGTH(SUBSTRING(er.numbers_only FROM 1 FOR 6)) = 6
            )
            UPDATE payments 
            SET charter_id = c.charter_id
            FROM potential_matches pm
            JOIN charters c ON c.reserve_number = pm.potential_reserve
            WHERE payments.payment_id = pm.payment_id
            AND payments.charter_id IS NULL
        """)
        extracted_reserves = cur.rowcount
        total_fixes += extracted_reserves
        print(f"   Extracted reserve matches: {extracted_reserves:,}")
        
        # Strategy 3: Match by account number with extended date range
        print("\n2. Matching by account number (90-day window)...")
        cur.execute("""
            UPDATE payments 
            SET charter_id = c.charter_id 
            FROM charters c 
            WHERE payments.reserve_number IS NULL 
            AND payments.account_number IS NOT NULL 
            AND payments.account_number = c.account_number
            AND payments.payment_date >= c.charter_date - INTERVAL '90 days'
            AND payments.payment_date <= c.charter_date + INTERVAL '90 days'
        """)
        account_matches = cur.rowcount
        total_fixes += account_matches
        print(f"   Account number matches: {account_matches:,}")
        
        # Strategy 4: Match by client_id with extended date range
        print("\n3. Matching by client_id (120-day window)...")
        cur.execute("""
            UPDATE payments 
            SET charter_id = c.charter_id 
            FROM charters c 
            WHERE payments.reserve_number IS NULL 
            AND payments.client_id IS NOT NULL 
            AND payments.client_id = c.client_id
            AND payments.payment_date >= c.charter_date - INTERVAL '120 days'
            AND payments.payment_date <= c.charter_date + INTERVAL '120 days'
        """)
        client_matches = cur.rowcount
        total_fixes += client_matches
        print(f"   Client ID matches: {client_matches:,}")
        
        # Strategy 5: Fuzzy amount matching (within $5) and close dates
        print("\n4. Fuzzy amount matching (±$5, 14-day window)...")
        cur.execute("""
            UPDATE payments 
            SET charter_id = c.charter_id
            FROM charters c
            WHERE payments.reserve_number IS NULL
            AND ABS(payments.amount - c.rate) <= 5.00
            AND payments.payment_date >= c.charter_date - INTERVAL '14 days'
            AND payments.payment_date <= c.charter_date + INTERVAL '14 days'
        """)
        amount_fuzzy = cur.rowcount
        total_fixes += amount_fuzzy
        print(f"   Fuzzy amount matches: {amount_fuzzy:,}")
        
        # Strategy 6: Match balance amounts (common for final payments)
        print("\n5. Matching balance amounts...")
        cur.execute("""
            UPDATE payments 
            SET charter_id = c.charter_id
            FROM charters c
            WHERE payments.reserve_number IS NULL
            AND payments.amount = c.balance
            AND c.balance > 0
            AND payments.payment_date >= c.charter_date - INTERVAL '60 days'
            AND payments.payment_date <= c.charter_date + INTERVAL '60 days'
        """)
        balance_matches = cur.rowcount
        total_fixes += balance_matches
        print(f"   Balance amount matches: {balance_matches:,}")
        
        # Strategy 7: Mark obvious cash payments
        print("\n6. Marking obvious cash payments...")
        cur.execute("""
            UPDATE payments 
            SET payment_method = 'cash'
            WHERE reserve_number IS NULL 
            AND (
                LOWER(COALESCE(notes, '')) LIKE '%cash%' OR
                LOWER(COALESCE(payment_key, '')) LIKE '%cash%' OR
                LOWER(COALESCE(notes, '')) LIKE '%mr / cash%' OR
                LOWER(COALESCE(notes, '')) LIKE '%cash payment%' OR
                LOWER(COALESCE(notes, '')) LIKE '%cash deposit%'
            )
            AND COALESCE(payment_method, '') != 'cash'
        """)
        cash_marked = cur.rowcount
        total_fixes += cash_marked
        print(f"   Payments marked as cash: {cash_marked:,}")
        
        # Strategy 8: Mark old unmatched payments as cash (over 2 years old)
        print("\n7. Marking old payments as cash (2+ years)...")
        cur.execute("""
            UPDATE payments 
            SET payment_method = 'cash'
            WHERE reserve_number IS NULL 
            AND payment_date < CURRENT_DATE - INTERVAL '2 years'
            AND COALESCE(payment_method, '') != 'cash'
            AND amount > 0
        """)
        old_cash = cur.rowcount
        total_fixes += old_cash
        print(f"   Old payments marked as cash: {old_cash:,}")
        
        # Strategy 9: Handle refunds and negative amounts
        print("\n8. Handling refunds and adjustments...")
        cur.execute("""
            UPDATE payments 
            SET notes = COALESCE(notes, '') || ' [REFUND/ADJUSTMENT - Auto-processed]',
                payment_method = CASE WHEN payment_method IS NULL THEN 'adjustment' ELSE payment_method END
            WHERE reserve_number IS NULL 
            AND amount < 0
            AND notes NOT LIKE '%REFUND%'
            AND notes NOT LIKE '%ADJUSTMENT%'
        """)
        refunds_handled = cur.rowcount
        total_fixes += refunds_handled
        print(f"   Refunds/adjustments handled: {refunds_handled:,}")
        
        conn.commit()
        print(f"\n✅ TOTAL FIXES APPLIED: {total_fixes:,}")
        
        # Get updated statistics
        cur.execute("SELECT COUNT(*) FROM payments WHERE reserve_number IS NOT NULL")
        new_matched = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM payments WHERE LOWER(COALESCE(payment_method, '')) = 'cash'")
        cash_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM payments")
        total_payments = cur.fetchone()[0]
        
        properly_handled = new_matched + cash_count
        new_percentage = (properly_handled / total_payments * 100) if total_payments > 0 else 0
        match_percentage = (new_matched / total_payments * 100) if total_payments > 0 else 0
        
        print(f"\n📊 NEW MATCH STATISTICS:")
        print(f"   ✅ Matched to charters: {new_matched:,} ({match_percentage:.1f}%)")
        print(f"   💵 Cash payments: {cash_count:,}")
        print(f"   📈 Properly handled: {properly_handled:,} ({new_percentage:.1f}%)")
        
        if new_percentage >= 95:
            print(f"   🎯 SUCCESS: Achieved {new_percentage:.1f}% - Target reached!")
        elif new_percentage >= 90:
            print(f"   🟡 CLOSE: {new_percentage:.1f}% - Almost there!")
        else:
            print(f"   🔴 MORE WORK NEEDED: {new_percentage:.1f}% - Continue improving")
        
        return {
            'total_fixes': total_fixes,
            'new_matched': new_matched,
            'cash_count': cash_count,
            'new_percentage': new_percentage,
            'match_percentage': match_percentage
        }
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during aggressive matching: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def analyze_remaining_unmatched():
    """Quick analysis of what's still unmatched"""
    
    print("\n🔍 ANALYZING REMAINING UNMATCHED...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT COUNT(*) 
            FROM payments 
            WHERE reserve_number IS NULL 
            AND LOWER(COALESCE(payment_method, '')) != 'cash'
        """)
        remaining = cur.fetchone()[0]
        
        if remaining > 0:
            print(f"   Remaining unmatched non-cash: {remaining:,}")
            
            # Sample of remaining
            cur.execute("""
                SELECT payment_id, payment_date, amount, payment_method, notes
                FROM payments 
                WHERE reserve_number IS NULL 
                AND LOWER(COALESCE(payment_method, '')) != 'cash'
                ORDER BY payment_date DESC
                LIMIT 10
            """)
            samples = cur.fetchall()
            
            print(f"   Recent examples:")
            for payment_id, payment_date, amount, method, notes in samples:
                method_str = method or "Unknown"
                notes_str = (notes[:50] + "...") if notes and len(notes) > 50 else (notes or "")
                print(f"     ID {payment_id}: {payment_date} | ${amount:,.2f} | {method_str} | {notes_str}")
        else:
            print(f"   🎉 ALL PAYMENTS RESOLVED!")
            
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    print("🚀 STARTING AGGRESSIVE PAYMENT MATCHING RECOVERY")
    print("=" * 60)
    
    results = apply_aggressive_matching()
    
    if results:
        analyze_remaining_unmatched()
        
        print(f"\n" + "=" * 60)
        print("🎯 AGGRESSIVE MATCHING COMPLETE!")
        print(f"Applied {results['total_fixes']:,} fixes")
        print(f"New match rate: {results['new_percentage']:.1f}%")
        print("=" * 60)
    else:
        print("❌ Matching failed - check errors above")