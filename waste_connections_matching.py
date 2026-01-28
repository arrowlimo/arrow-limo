#!/usr/bin/env python3
"""
Waste Connections Payment Matching
Handle specific Waste Connections payment patterns from 2015+ with penny adjustments
"""

import sys
import os
sys.path.insert(0, os.getcwd())

from api import get_db_connection

def analyze_waste_connections_patterns():
    """Analyze Waste Connections payment patterns"""
    
    print("🗑️ ANALYZING WASTE CONNECTIONS PAYMENT PATTERNS...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Find Waste Connections related payments
        print("\n1. Finding Waste Connections payments...")
        cur.execute("""
            SELECT 
                p.payment_id, p.payment_date, p.amount, p.payment_method, 
                p.notes, p.reserve_number, p.account_number, p.client_id
            FROM payments p
            LEFT JOIN clients c ON p.client_id = c.client_id
            WHERE (
                LOWER(COALESCE(p.notes, '')) LIKE '%waste%' OR
                LOWER(COALESCE(p.notes, '')) LIKE '%connections%' OR
                LOWER(COALESCE(c.client_name, '')) LIKE '%waste%' OR
                LOWER(COALESCE(c.client_name, '')) LIKE '%connections%' OR
                p.account_number IN (
                    SELECT DISTINCT c2.account_number 
                    FROM charters c2 
                    JOIN clients cl ON c2.client_id = cl.client_id
                    WHERE LOWER(cl.client_name) LIKE '%waste%'
                )
            )
            AND p.payment_date >= '2015-01-01'
            ORDER BY p.payment_date DESC
            LIMIT 20
        """)
        
        waste_payments = cur.fetchall()
        print(f"   Found {len(waste_payments)} Waste Connections payments since 2015:")
        
        for payment_id, payment_date, amount, method, notes, reserve_num, account_num, client_id in waste_payments:
            method_str = method or "Unknown"
            notes_str = (notes[:60] + "...") if notes and len(notes) > 60 else (notes or "")
            print(f"     ID {payment_id}: {payment_date} | ${amount:,.2f} | {method_str}")
            print(f"       Notes: {notes_str}")
            print(f"       Reserve: {reserve_num} | Account: {account_num}")
        
        # Find regular recurring amounts for Waste Connections
        print(f"\n2. Finding regular payment amounts...")
        cur.execute("""
            SELECT 
                ROUND(amount, 2) as rounded_amount,
                COUNT(*) as frequency,
                MIN(payment_date) as first_date,
                MAX(payment_date) as last_date
            FROM payments p
            LEFT JOIN clients c ON p.client_id = c.client_id
            WHERE (
                LOWER(COALESCE(p.notes, '')) LIKE '%waste%' OR
                LOWER(COALESCE(c.client_name, '')) LIKE '%waste%'
            )
            AND p.payment_date >= '2015-01-01'
            GROUP BY ROUND(amount, 2)
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC, rounded_amount DESC
        """)
        
        regular_amounts = cur.fetchall()
        print(f"   Regular payment amounts:")
        for amount, freq, first_date, last_date in regular_amounts:
            print(f"     ${amount:,.2f}: {freq:,} payments ({first_date} to {last_date})")
        
        # Find charters that match these regular amounts
        if regular_amounts:
            regular_amount_list = [str(amount) for amount, freq, first_date, last_date in regular_amounts]
            amount_filter = ','.join(regular_amount_list)
            
            print(f"\n3. Finding charters with matching rates...")
            cur.execute(f"""
                SELECT 
                    c.charter_id, c.charter_date, c.rate, c.balance, c.reserve_number,
                    cl.client_name
                FROM charters c
                LEFT JOIN clients cl ON c.client_id = cl.client_id
                WHERE c.rate IN ({amount_filter})
                AND (
                    LOWER(COALESCE(cl.client_name, '')) LIKE '%waste%' OR
                    c.charter_date >= '2015-01-01'
                )
                ORDER BY c.charter_date DESC
                LIMIT 15
            """)
            
            matching_charters = cur.fetchall()
            print(f"   Found {len(matching_charters)} charters with matching rates:")
            for charter_id, charter_date, rate, balance, reserve_num, client_name in matching_charters:
                client_str = client_name or "Unknown Client"
                print(f"     Charter {charter_id}: {charter_date} | Rate: ${rate:,.2f} | Balance: ${balance:,.2f}")
                print(f"       Reserve: {reserve_num} | Client: {client_str}")
        
        return waste_payments, regular_amounts
        
    finally:
        cur.close()
        conn.close()

def match_waste_connections_payments():
    """Apply specific matching for Waste Connections payments"""
    
    print("\n🔧 APPLYING WASTE CONNECTIONS PAYMENT MATCHING...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        total_fixes = 0
        
        # Strategy 1: Match by client name pattern
        print("\n1. Matching by Waste Connections client pattern...")
        cur.execute("""
            UPDATE payments 
            SET charter_id = c.charter_id
            FROM charters c
            JOIN clients cl ON c.client_id = cl.client_id
            WHERE payments.reserve_number IS NULL
            AND payments.client_id = c.client_id
            AND LOWER(cl.client_name) LIKE '%waste%'
            AND payments.payment_date >= c.charter_date - INTERVAL '60 days'
            AND payments.payment_date <= c.charter_date + INTERVAL '60 days'
        """)
        client_matches = cur.rowcount
        total_fixes += client_matches
        print(f"   Client pattern matches: {client_matches:,}")
        
        # Strategy 2: Match regular amounts with penny tolerance
        print("\n2. Matching with penny tolerance (±$0.05)...")
        cur.execute("""
            UPDATE payments 
            SET charter_id = c.charter_id
            FROM charters c
            JOIN clients cl ON c.client_id = cl.client_id
            WHERE payments.reserve_number IS NULL
            AND LOWER(COALESCE(cl.client_name, '')) LIKE '%waste%'
            AND ABS(payments.amount - c.rate) <= 0.05
            AND payments.payment_date >= '2015-01-01'
            AND payments.payment_date >= c.charter_date - INTERVAL '90 days'
            AND payments.payment_date <= c.charter_date + INTERVAL '90 days'
        """)
        penny_matches = cur.rowcount
        total_fixes += penny_matches
        print(f"   Penny tolerance matches: {penny_matches:,}")
        
        # Strategy 3: Match Square payments for Waste Connections
        print("\n3. Matching Square payments to Waste Connections...")
        cur.execute("""
            UPDATE payments 
            SET charter_id = c.charter_id
            FROM charters c
            JOIN clients cl ON c.client_id = cl.client_id
            WHERE payments.reserve_number IS NULL
            AND (
                LOWER(COALESCE(payments.notes, '')) LIKE '%square%' OR
                payments.payment_method = 'credit_card'
            )
            AND LOWER(COALESCE(cl.client_name, '')) LIKE '%waste%'
            AND ABS(payments.amount - c.rate) <= 2.00
            AND payments.payment_date >= c.charter_date - INTERVAL '30 days'
            AND payments.payment_date <= c.charter_date + INTERVAL '30 days'
        """)
        square_matches = cur.rowcount
        total_fixes += square_matches
        print(f"   Square payment matches: {square_matches:,}")
        
        # Strategy 4: Match by account number for regular service
        print("\n4. Matching by account number (regular service)...")
        cur.execute("""
            UPDATE payments 
            SET charter_id = c.charter_id
            FROM charters c
            WHERE payments.reserve_number IS NULL
            AND payments.account_number IS NOT NULL
            AND payments.account_number = c.account_number
            AND payments.payment_date >= '2015-01-01'
            AND ABS(payments.amount - c.rate) <= 1.00
            AND payments.payment_date >= c.charter_date - INTERVAL '120 days'
            AND payments.payment_date <= c.charter_date + INTERVAL '120 days'
        """)
        account_matches = cur.rowcount
        total_fixes += account_matches
        print(f"   Account number matches: {account_matches:,}")
        
        # Strategy 5: Handle penny adjustment charges
        print("\n5. Creating penny adjustment entries...")
        cur.execute("""
            SELECT 
                p.payment_id, p.amount, c.charter_id, c.rate,
                (p.amount - c.rate) as difference
            FROM payments p
            JOIN charters c ON p.charter_id = c.charter_id
            JOIN clients cl ON c.client_id = cl.client_id
            WHERE LOWER(cl.client_name) LIKE '%waste%'
            AND ABS(p.amount - c.rate) BETWEEN 0.01 AND 0.10
            AND p.payment_date >= '2015-01-01'
            LIMIT 10
        """)
        
        penny_adjustments = cur.fetchall()
        if penny_adjustments:
            print(f"   Found {len(penny_adjustments)} payments with penny differences:")
            for payment_id, amount, charter_id, rate, diff in penny_adjustments:
                print(f"     Payment {payment_id}: ${amount:.2f} vs Rate ${rate:.2f} (diff: ${diff:.2f})")
        
        conn.commit()
        print(f"\n✅ WASTE CONNECTIONS FIXES APPLIED: {total_fixes:,}")
        
        return total_fixes
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error in Waste Connections matching: {e}")
        return 0
    finally:
        cur.close()
        conn.close()

def apply_general_business_patterns():
    """Apply other business-specific patterns for better matching"""
    
    print("\n🏢 APPLYING GENERAL BUSINESS PATTERN MATCHING...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        total_fixes = 0
        
        # Strategy 1: Match regular corporate accounts by amount patterns
        print("\n1. Matching regular corporate accounts...")
        cur.execute("""
            WITH regular_amounts AS (
                SELECT 
                    account_number,
                    rate,
                    COUNT(*) as frequency
                FROM charters 
                WHERE account_number IS NOT NULL
                AND charter_date >= '2015-01-01'
                GROUP BY account_number, rate
                HAVING COUNT(*) >= 3
            )
            UPDATE payments 
            SET charter_id = c.charter_id
            FROM charters c
            JOIN regular_amounts ra ON c.account_number = ra.account_number AND c.rate = ra.rate
            WHERE payments.reserve_number IS NULL
            AND payments.account_number = c.account_number
            AND ABS(payments.amount - c.rate) <= 0.10
            AND payments.payment_date >= c.charter_date - INTERVAL '90 days'
            AND payments.payment_date <= c.charter_date + INTERVAL '90 days'
        """)
        regular_corporate = cur.rowcount
        total_fixes += regular_corporate
        print(f"   Regular corporate matches: {regular_corporate:,}")
        
        # Strategy 2: Match by similar amounts on same day
        print("\n2. Matching by similar amounts same day...")
        cur.execute("""
            UPDATE payments 
            SET charter_id = c.charter_id
            FROM charters c
            WHERE payments.reserve_number IS NULL
            AND payments.payment_date = c.charter_date
            AND ABS(payments.amount - c.rate) <= 0.25
            AND payments.payment_date >= '2015-01-01'
        """)
        same_day_matches = cur.rowcount
        total_fixes += same_day_matches
        print(f"   Same day amount matches: {same_day_matches:,}")
        
        # Strategy 3: Check payment method patterns
        print("\n3. Matching check payments (likely corporate)...")
        cur.execute("""
            UPDATE payments 
            SET charter_id = c.charter_id
            FROM charters c
            WHERE payments.reserve_number IS NULL
            AND payments.payment_method = 'check'
            AND ABS(payments.amount - c.rate) <= 0.05
            AND payments.payment_date >= c.charter_date - INTERVAL '45 days'
            AND payments.payment_date <= c.charter_date + INTERVAL '45 days'
        """)
        check_matches = cur.rowcount
        total_fixes += check_matches
        print(f"   Check payment matches: {check_matches:,}")
        
        conn.commit()
        print(f"\n✅ BUSINESS PATTERN FIXES APPLIED: {total_fixes:,}")
        
        return total_fixes
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error in business pattern matching: {e}")
        return 0
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    print("🗑️ WASTE CONNECTIONS & BUSINESS PATTERN MATCHING")
    print("=" * 60)
    
    # Analyze patterns first
    waste_payments, regular_amounts = analyze_waste_connections_patterns()
    
    # Apply specific fixes
    waste_fixes = match_waste_connections_payments()
    business_fixes = apply_general_business_patterns()
    
    total_all_fixes = waste_fixes + business_fixes
    
    print(f"\n" + "=" * 60)
    print("🎯 BUSINESS PATTERN MATCHING COMPLETE!")
    print(f"Waste Connections fixes: {waste_fixes:,}")
    print(f"Business pattern fixes: {business_fixes:,}")
    print(f"Total fixes applied: {total_all_fixes:,}")
    print("=" * 60)