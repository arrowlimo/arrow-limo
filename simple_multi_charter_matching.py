#!/usr/bin/env python3
"""
Fixed Multi-Charter Payment Matching
Simpler approach to match payments covering multiple charters
"""

import sys
import os
sys.path.insert(0, os.getcwd())

from api import get_db_connection

def simple_multi_charter_matching():
    """Apply simplified multi-charter payment matching"""
    
    print("💰 SIMPLIFIED MULTI-CHARTER PAYMENT MATCHING...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        total_fixes = 0
        
        # Strategy 1: Check if large unmatched payments match sum of unmatched charters by client
        print("\n1. Checking large payments against multiple charters by client...")
        
        # Find large unmatched payments with client_id
        cur.execute("""
            SELECT p.payment_id, p.amount, p.client_id, p.payment_date
            FROM payments p 
            WHERE p.reserve_number IS NULL 
            AND p.client_id IS NOT NULL
            AND p.amount > 500
            ORDER BY p.amount DESC
            LIMIT 50
        """)
        
        large_payments = cur.fetchall()
        matched_this_round = 0
        
        for payment_id, amount, client_id, payment_date in large_payments:
            # Find unmatched charters for this client around this time
            cur.execute("""
                SELECT charter_id, charter_date, rate, balance
                FROM charters 
                WHERE client_id = %s
                AND charter_date >= %s - INTERVAL '120 days'
                AND charter_date <= %s + INTERVAL '120 days'
                AND rate > 0
                ORDER BY charter_date
            """, (client_id, payment_date, payment_date))
            
            charters = cur.fetchall()
            
            if len(charters) >= 2:  # Multiple charters
                total_charter_amount = sum(rate for _, _, rate, _ in charters)
                
                # Check if payment amount matches total (within tolerance)
                if abs(amount - total_charter_amount) <= 50.00:
                    # Match to earliest charter
                    earliest_charter_id = charters[0][0]
                    
                    cur.execute("""
                        UPDATE payments 
                        SET charter_id = %s,
                            notes = COALESCE(notes, '') || ' [Multi-charter: $' || %s || ' covers ' || %s || ' charters]'
                        WHERE payment_id = %s
                    """, (earliest_charter_id, str(total_charter_amount), len(charters), payment_id))
                    
                    if cur.rowcount > 0:
                        matched_this_round += 1
                        print(f"   Payment {payment_id}: ${amount:,.2f} → {len(charters)} charters (${total_charter_amount:,.2f})")
        
        total_fixes += matched_this_round
        print(f"   Multi-charter client matches: {matched_this_round:,}")
        
        # Strategy 2: Check by account number
        print("\n2. Checking large payments against multiple charters by account...")
        
        cur.execute("""
            SELECT p.payment_id, p.amount, p.account_number, p.payment_date
            FROM payments p 
            WHERE p.reserve_number IS NULL 
            AND p.account_number IS NOT NULL
            AND p.amount > 500
            ORDER BY p.amount DESC
            LIMIT 50
        """)
        
        account_payments = cur.fetchall()
        matched_account = 0
        
        for payment_id, amount, account_number, payment_date in account_payments:
            # Find charters for this account around this time
            cur.execute("""
                SELECT charter_id, charter_date, rate, balance
                FROM charters 
                WHERE account_number = %s
                AND charter_date >= %s - INTERVAL '120 days'
                AND charter_date <= %s + INTERVAL '120 days'
                AND rate > 0
                ORDER BY charter_date
            """, (account_number, payment_date, payment_date))
            
            charters = cur.fetchall()
            
            if len(charters) >= 2:  # Multiple charters
                total_charter_amount = sum(rate for _, _, rate, _ in charters)
                
                # Check if payment amount matches total (within tolerance)
                if abs(amount - total_charter_amount) <= 100.00:  # More tolerance for account-based
                    # Match to earliest charter
                    earliest_charter_id = charters[0][0]
                    
                    cur.execute("""
                        UPDATE payments 
                        SET charter_id = %s,
                            notes = COALESCE(notes, '') || ' [Multi-charter account: $' || %s || ' covers ' || %s || ' charters]'
                        WHERE payment_id = %s
                        AND charter_id IS NULL
                    """, (earliest_charter_id, str(total_charter_amount), len(charters), payment_id))
                    
                    if cur.rowcount > 0:
                        matched_account += 1
                        print(f"   Payment {payment_id}: ${amount:,.2f} → {len(charters)} charters (${total_charter_amount:,.2f})")
        
        total_fixes += matched_account
        print(f"   Multi-charter account matches: {matched_account:,}")
        
        # Strategy 3: Match partial payments to charter balances...
        print("\n3. Matching partial payments to charter balances...")
        
        cur.execute("""
            UPDATE payments 
            SET charter_id = c.charter_id,
                notes = COALESCE(payments.notes, '') || ' [Partial payment matched to balance]'
            FROM charters c
            WHERE payments.reserve_number IS NULL
            AND payments.client_id = c.client_id
            AND payments.amount = c.balance
            AND c.balance > 0
            AND payments.payment_date >= c.charter_date - INTERVAL '90 days'
            AND payments.payment_date <= c.charter_date + INTERVAL '90 days'
        """)
        
        partial_matches = cur.rowcount
        total_fixes += partial_matches
        print(f"   Partial/balance matches: {partial_matches:,}")
        
        # Strategy 4: Match by client with date and amount proximity
        print("\n4. Liberal client-based matching...")
        
        cur.execute("""
            UPDATE payments 
            SET charter_id = c.charter_id,
                notes = COALESCE(payments.notes, '') || ' [Client-based liberal match]'
            FROM charters c
            WHERE payments.reserve_number IS NULL
            AND payments.client_id = c.client_id
            AND ABS(payments.amount - c.rate) <= 100.00
            AND payments.payment_date >= c.charter_date - INTERVAL '180 days'
            AND payments.payment_date <= c.charter_date + INTERVAL '180 days'
            AND payments.amount > 200
        """)
        
        liberal_matches = cur.rowcount
        total_fixes += liberal_matches
        print(f"   Liberal client matches: {liberal_matches:,}")
        
        conn.commit()
        print(f"\n✅ TOTAL MULTI-CHARTER FIXES: {total_fixes:,}")
        
        return total_fixes
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error in multi-charter matching: {e}")
        return 0
    finally:
        cur.close()
        conn.close()

def check_current_status():
    """Check current payment matching status after multi-charter fixes"""
    
    print("\n📊 CHECKING UPDATED PAYMENT STATUS...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get current statistics
        cur.execute("SELECT COUNT(*) FROM payments")
        total_payments = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM payments WHERE reserve_number IS NOT NULL")
        matched_payments = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM payments WHERE reserve_number IS NULL")
        unmatched_payments = cur.fetchone()[0]
        
        match_percentage = (matched_payments / total_payments * 100) if total_payments > 0 else 0
        
        print(f"   Total payments: {total_payments:,}")
        print(f"   ✅ Matched: {matched_payments:,} ({match_percentage:.1f}%)")
        print(f"   ❌ Unmatched: {unmatched_payments:,}")
        
        # Check for cash payments
        cur.execute("SELECT COUNT(*) FROM payments WHERE LOWER(COALESCE(payment_method, '')) = 'cash'")
        cash_payments = cur.fetchone()[0]
        
        properly_handled = matched_payments + cash_payments
        total_percentage = (properly_handled / total_payments * 100) if total_payments > 0 else 0
        
        print(f"   💵 Cash payments: {cash_payments:,}")
        print(f"   📈 Properly handled: {properly_handled:,} ({total_percentage:.1f}%)")
        
        if total_percentage >= 98:
            print(f"   🎉 TARGET ACHIEVED: {total_percentage:.1f}%!")
        elif total_percentage >= 95:
            print(f"   🟡 VERY CLOSE: {total_percentage:.1f}%")
        elif total_percentage >= 90:
            print(f"   🟠 GOOD PROGRESS: {total_percentage:.1f}%")
        else:
            print(f"   🔴 MORE WORK NEEDED: {total_percentage:.1f}%")
        
        return {
            'total_payments': total_payments,
            'matched_payments': matched_payments,
            'cash_payments': cash_payments,
            'total_percentage': total_percentage
        }
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    print("🔄 MULTI-CHARTER PAYMENT MATCHING - SIMPLIFIED APPROACH")
    print("=" * 60)
    
    # Apply multi-charter matching
    fixes = simple_multi_charter_matching()
    
    # Check updated status
    status = check_current_status()
    
    print(f"\n" + "=" * 60)
    print("💰 MULTI-CHARTER MATCHING RESULTS")
    print(f"Applied {fixes:,} multi-charter fixes")
    if status:
        print(f"New match rate: {status['total_percentage']:.1f}%")
    print("=" * 60)