#!/usr/bin/env python3
"""
Multi-Charter Payment Analysis
Analyze and match payments that cover multiple charter runs for the same customer
"""

import sys
import os
sys.path.insert(0, os.getcwd())

from api import get_db_connection
from datetime import datetime, timedelta

def analyze_multi_charter_patterns():
    """Analyze patterns of payments that might cover multiple charters"""
    
    print("🔍 ANALYZING MULTI-CHARTER PAYMENT PATTERNS...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Find unmatched payments that might be multi-charter payments
        print("\n1. Finding large unmatched payments (potential multi-charter)...")
        cur.execute("""
            SELECT 
                p.payment_id, p.payment_date, p.amount, p.payment_method,
                p.client_id, p.account_number, p.notes,
                c.client_name
            FROM payments p
            LEFT JOIN clients c ON p.client_id = c.client_id
            WHERE p.reserve_number IS NULL
            AND p.amount > 500  -- Large payments likely to be multi-charter
            AND p.payment_date >= '2015-01-01'
            ORDER BY p.amount DESC
            LIMIT 20
        """)
        
        large_payments = cur.fetchall()
        print(f"   Found {len(large_payments)} large unmatched payments:")
        
        for payment_id, payment_date, amount, method, client_id, account_num, notes, client_name in large_payments:
            client_str = client_name or f"Client ID {client_id}" if client_id else "Unknown"
            method_str = method or "Unknown"
            notes_str = (notes[:50] + "...") if notes and len(notes) > 50 else (notes or "")
            print(f"     Payment {payment_id}: {payment_date} | ${amount:,.2f} | {method_str}")
            print(f"       Client: {client_str} | Account: {account_num}")
            print(f"       Notes: {notes_str}")
        
        # Find customers with multiple charters around payment dates
        print(f"\n2. Finding customers with multiple charters near payment dates...")
        for payment_id, payment_date, amount, method, client_id, account_num, notes, client_name in large_payments[:5]:
            if client_id or account_num:
                print(f"\n   Analyzing payment {payment_id} (${amount:,.2f}) for multi-charter match:")
                
                # Find charters for this customer around the payment date
                if client_id:
                    cur.execute("""
                        SELECT 
                            charter_id, charter_date, rate, balance, reserve_number,
                            ABS(EXTRACT(DAYS FROM (charter_date - %s))) as days_diff
                        FROM charters 
                        WHERE client_id = %s
                        AND charter_date >= %s - INTERVAL '60 days'
                        AND charter_date <= %s + INTERVAL '60 days'
                        ORDER BY charter_date
                    """, (payment_date, client_id, payment_date, payment_date))
                elif account_num:
                    cur.execute("""
                        SELECT 
                            charter_id, charter_date, rate, balance, reserve_number,
                            ABS(EXTRACT(DAYS FROM (charter_date - %s))) as days_diff
                        FROM charters 
                        WHERE account_number = %s
                        AND charter_date >= %s - INTERVAL '60 days'
                        AND charter_date <= %s + INTERVAL '60 days'
                        ORDER BY charter_date
                    """, (payment_date, account_num, payment_date, payment_date))
                else:
                    continue
                    
                nearby_charters = cur.fetchall()
                
                if nearby_charters:
                    total_charter_amount = sum(rate for _, _, rate, _, _, _ in nearby_charters if rate)
                    print(f"     Found {len(nearby_charters)} nearby charters, total: ${total_charter_amount:,.2f}")
                    
                    for charter_id, charter_date, rate, balance, reserve_num, days_diff in nearby_charters:
                        print(f"       Charter {charter_id}: {charter_date} | ${rate:,.2f} | Reserve {reserve_num} | {days_diff} days")
                    
                    # Check if payment amount matches total of multiple charters
                    if abs(amount - total_charter_amount) <= 10.00:
                        print(f"     🎯 POTENTIAL MATCH: Payment ${amount:,.2f} ≈ Charters ${total_charter_amount:,.2f}")
                    elif abs(amount - total_charter_amount) <= 50.00:
                        print(f"     🟡 CLOSE MATCH: Payment ${amount:,.2f} vs Charters ${total_charter_amount:,.2f}")
        
        return large_payments
        
    finally:
        cur.close()
        conn.close()

def match_multi_charter_payments():
    """Apply multi-charter payment matching"""
    
    print("\n🔧 APPLYING MULTI-CHARTER PAYMENT MATCHING...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        total_fixes = 0
        
        # Strategy 1: Match payments to the earliest charter when amount matches multiple charters
        print("\n1. Matching multi-charter payments to earliest charter...")
        
        # Find payments where the amount matches sum of multiple charters for same customer
        cur.execute("""
            WITH payment_charter_sums AS (
                SELECT DISTINCT
                    p.payment_id,
                    p.amount as payment_amount,
                    p.client_id,
                    p.account_number,
                    p.payment_date,
                    (
                        SELECT SUM(c.rate)
                        FROM charters c
                        WHERE (
                            (p.client_id IS NOT NULL AND c.client_id = p.client_id) OR
                            (p.account_number IS NOT NULL AND c.account_number = p.account_number)
                        )
                        AND c.charter_date >= p.payment_date - INTERVAL '60 days'
                        AND c.charter_date <= p.payment_date + INTERVAL '60 days'
                        AND c.rate > 0
                    ) as charter_sum,
                    (
                        SELECT MIN(c.charter_id)
                        FROM charters c
                        WHERE (
                            (p.client_id IS NOT NULL AND c.client_id = p.client_id) OR
                            (p.account_number IS NOT NULL AND c.account_number = p.account_number)
                        )
                        AND c.charter_date >= p.payment_date - INTERVAL '60 days'
                        AND c.charter_date <= p.payment_date + INTERVAL '60 days'
                        AND c.rate > 0
                        ORDER BY c.charter_date
                    ) as earliest_charter_id
                FROM payments p
                WHERE p.reserve_number IS NULL
                AND p.amount > 200  -- Minimum for multi-charter
                AND (p.client_id IS NOT NULL OR p.account_number IS NOT NULL)
            )
            UPDATE payments
            SET charter_id = pcs.earliest_charter_id,
                notes = COALESCE(notes, '') || ' [Multi-charter payment matched]'
            FROM payment_charter_sums pcs
            WHERE payments.payment_id = pcs.payment_id
            AND pcs.charter_sum IS NOT NULL
            AND ABS(pcs.payment_amount - pcs.charter_sum) <= 25.00  -- Allow $25 tolerance
            AND payments.charter_id IS NULL
        """)
        
        multi_charter_matches = cur.rowcount
        total_fixes += multi_charter_matches
        print(f"   Multi-charter matches: {multi_charter_matches:,}")
        
        # Strategy 2: Match large payments to customers with outstanding balances
        print("\n2. Matching large payments to outstanding balances...")
        cur.execute("""
            WITH customer_balances AS (
                SELECT 
                    p.payment_id,
                    p.amount,
                    p.client_id,
                    p.account_number,
                    (
                        SELECT SUM(c.balance)
                        FROM charters c
                        WHERE (
                            (p.client_id IS NOT NULL AND c.client_id = p.client_id) OR
                            (p.account_number IS NOT NULL AND c.account_number = p.account_number)
                        )
                        AND c.balance > 0
                        AND c.charter_date <= p.payment_date + INTERVAL '30 days'
                    ) as total_balance,
                    (
                        SELECT MIN(c.charter_id)
                        FROM charters c
                        WHERE (
                            (p.client_id IS NOT NULL AND c.client_id = p.client_id) OR
                            (p.account_number IS NOT NULL AND c.account_number = p.account_number)
                        )
                        AND c.balance > 0
                        AND c.charter_date <= p.payment_date + INTERVAL '30 days'
                        ORDER BY c.charter_date
                    ) as earliest_charter_id
                FROM payments p
                WHERE p.reserve_number IS NULL
                AND p.amount > 100
                AND (p.client_id IS NOT NULL OR p.account_number IS NOT NULL)
            )
            UPDATE payments
            SET charter_id = cb.earliest_charter_id,
                notes = COALESCE(notes, '') || ' [Balance payment matched]'
            FROM customer_balances cb
            WHERE payments.payment_id = cb.payment_id
            AND cb.total_balance IS NOT NULL
            AND ABS(payments.amount - cb.total_balance) <= 20.00
            AND payments.charter_id IS NULL
        """)
        
        balance_matches = cur.rowcount
        total_fixes += balance_matches
        print(f"   Balance payment matches: {balance_matches:,}")
        
        # Strategy 3: Match by customer and approximate timing for regular customers
        print("\n3. Matching regular customers by pattern...")
        cur.execute("""
            WITH regular_customers AS (
                SELECT 
                    client_id,
                    account_number,
                    COUNT(*) as charter_count,
                    AVG(rate) as avg_rate
                FROM charters
                WHERE charter_date >= '2020-01-01'
                AND (client_id IS NOT NULL OR account_number IS NOT NULL)
                GROUP BY client_id, account_number
                HAVING COUNT(*) >= 5  -- Regular customers
            )
            UPDATE payments
            SET charter_id = c.charter_id,
                notes = COALESCE(notes, '') || ' [Regular customer pattern matched]'
            FROM charters c
            JOIN regular_customers rc ON (
                (c.client_id IS NOT NULL AND c.client_id = rc.client_id) OR
                (c.account_number IS NOT NULL AND c.account_number = rc.account_number)
            )
            WHERE payments.reserve_number IS NULL
            AND (
                (payments.client_id IS NOT NULL AND payments.client_id = rc.client_id) OR
                (payments.account_number IS NOT NULL AND payments.account_number = rc.account_number)
            )
            AND ABS(payments.amount - c.rate) <= 50.00
            AND payments.payment_date >= c.charter_date - INTERVAL '90 days'
            AND payments.payment_date <= c.charter_date + INTERVAL '90 days'
        """)
        
        regular_customer_matches = cur.rowcount
        total_fixes += regular_customer_matches
        print(f"   Regular customer matches: {regular_customer_matches:,}")
        
        conn.commit()
        print(f"\n✅ MULTI-CHARTER MATCHING COMPLETE: {total_fixes:,} fixes applied")
        
        return total_fixes
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error in multi-charter matching: {e}")
        return 0
    finally:
        cur.close()
        conn.close()

def verify_multi_charter_matches():
    """Verify the multi-charter matches we just made"""
    
    print("\n📊 VERIFYING MULTI-CHARTER MATCHES...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check payments with multi-charter notes
        cur.execute("""
            SELECT 
                p.payment_id, p.payment_date, p.amount, p.charter_id,
                c.charter_date, c.rate, c.balance, c.reserve_number,
                cl.client_name
            FROM payments p
            JOIN charters c ON p.charter_id = c.charter_id
            LEFT JOIN clients cl ON c.client_id = cl.client_id
            WHERE p.notes LIKE '%Multi-charter%' OR p.notes LIKE '%Balance payment%'
            ORDER BY p.payment_date DESC
            LIMIT 10
        """)
        
        verified_matches = cur.fetchall()
        
        if verified_matches:
            print(f"   Verified {len(verified_matches)} multi-charter matches:")
            for payment_id, payment_date, amount, charter_id, charter_date, rate, balance, reserve_num, client_name in verified_matches:
                client_str = client_name or "Unknown"
                print(f"     Payment {payment_id}: ${amount:,.2f} → Charter {charter_id} (${rate:,.2f})")
                print(f"       Dates: Payment {payment_date} | Charter {charter_date}")
                print(f"       Client: {client_str} | Reserve: {reserve_num}")
        else:
            print("   No multi-charter matches found to verify")
            
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    print("💰 MULTI-CHARTER PAYMENT ANALYSIS & MATCHING")
    print("=" * 60)
    
    # Analyze patterns first
    large_payments = analyze_multi_charter_patterns()
    
    # Apply multi-charter matching
    fixes = match_multi_charter_payments()
    
    # Verify results
    verify_multi_charter_matches()
    
    print(f"\n" + "=" * 60)
    print("💰 MULTI-CHARTER MATCHING COMPLETE!")
    print(f"Applied {fixes:,} multi-charter fixes")
    print("=" * 60)