#!/usr/bin/env python3
"""
Bank Transfer Payment Analysis
Analyzes the 23,222 unmatched bank transfer payments to find matching patterns
"""

import sys
import os
sys.path.insert(0, os.getcwd())

from api import get_db_connection
import re
from datetime import datetime, timedelta

def analyze_bank_transfer_patterns():
    """Analyze unmatched bank transfer payments for patterns"""
    
    print("🏦 Analyzing Bank Transfer Payment Patterns...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get sample of unmatched bank transfers
        cur.execute("""
            SELECT payment_id, payment_date, amount, notes, payment_key, reserve_number, account_number
            FROM payments 
            WHERE reserve_number IS NULL 
            AND payment_method = 'bank_transfer'
            ORDER BY payment_date DESC
            LIMIT 50
        """)
        samples = cur.fetchall()
        
        print(f"\n📋 Sample of {len(samples)} Recent Unmatched Bank Transfers:")
        
        lms_deposit_pattern = re.compile(r'\[LMS Deposit (\d+)\]')
        reserve_pattern = re.compile(r'(\d{6})')
        
        patterns = {
            'lms_deposits': 0,
            'has_reserve_in_notes': 0,
            'has_account_number': 0,
            'negative_amounts': 0,
            'recent_payments': 0
        }
        
        potential_matches = []
        
        for payment_id, payment_date, amount, notes, payment_key, reserve_number, account_number in samples:
            print(f"   ID {payment_id}: {payment_date} | ${amount:,.2f}")
            print(f"      Notes: {notes}")
            print(f"      Reserve: {reserve_number} | Account: {account_number}")
            
            # Analyze patterns
            if notes and '[LMS Deposit' in notes:
                patterns['lms_deposits'] += 1
                
            if notes and reserve_pattern.search(notes):
                patterns['has_reserve_in_notes'] += 1
                # Extract potential reserve number from notes
                match = reserve_pattern.search(notes)
                if match:
                    potential_reserve = match.group(1)
                    potential_matches.append({
                        'payment_id': payment_id,
                        'potential_reserve': potential_reserve,
                        'amount': amount,
                        'date': payment_date
                    })
                    
            if account_number:
                patterns['has_account_number'] += 1
                
            if amount < 0:
                patterns['negative_amounts'] += 1
                
            if payment_date and payment_date >= datetime.now().date() - timedelta(days=90):
                patterns['recent_payments'] += 1
                
            print()
        
        print("📊 Pattern Analysis:")
        print(f"   LMS Deposits: {patterns['lms_deposits']}")
        print(f"   Reserve numbers in notes: {patterns['has_reserve_in_notes']}")
        print(f"   Have account numbers: {patterns['has_account_number']}")
        print(f"   Negative amounts: {patterns['negative_amounts']}")
        print(f"   Recent (90 days): {patterns['recent_payments']}")
        
        # Check potential matches
        if potential_matches:
            print(f"\n🔍 Checking {len(potential_matches)} Potential Reserve Number Matches:")
            
            for match in potential_matches[:10]:  # Check first 10
                cur.execute("""
                    SELECT charter_id, charter_date, client_id, rate, balance 
                    FROM charters 
                    WHERE reserve_number = %s
                """, (match['potential_reserve'],))
                charter = cur.fetchone()
                
                if charter:
                    charter_id, charter_date, client_id, rate, balance = charter
                    date_diff = abs((match['date'] - charter_date).days) if charter_date else 999
                    print(f"   Payment {match['payment_id']} → Reserve {match['potential_reserve']}")
                    print(f"     Charter: {charter_date} | Rate: ${rate} | Balance: ${balance}")
                    print(f"     Date diff: {date_diff} days | Amount match: {abs(match['amount'] - (rate or 0)) < 5}")
                    
        return patterns
        
    finally:
        cur.close()
        conn.close()

def apply_bank_transfer_fixes():
    """Apply fixes specific to bank transfer patterns"""
    
    print("\n🔧 Applying Bank Transfer Specific Fixes...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        fixes_applied = 0
        
        # Fix 1: Extract reserve numbers from LMS Deposit notes
        print("\n1. Matching by reserve numbers in LMS Deposit notes...")
        cur.execute("""
            WITH extracted_reserves AS (
                SELECT 
                    p.payment_id,
                    p.notes,
                    SUBSTRING(p.notes FROM '(\d{6})') as extracted_reserve
                FROM payments p
                WHERE p.reserve_number IS NULL 
                AND p.payment_method = 'bank_transfer'
                AND p.notes LIKE '%LMS Deposit%'
                AND p.notes ~ '\d{6}'
            )
            UPDATE payments 
            SET charter_id = c.charter_id
            FROM extracted_reserves er
            JOIN charters c ON c.reserve_number = er.extracted_reserve
            WHERE payments.payment_id = er.payment_id
            AND payments.charter_id IS NULL
        """)
        lms_fixes = cur.rowcount
        fixes_applied += lms_fixes
        print(f"   Fixed {lms_fixes:,} payments by extracting reserve numbers from LMS notes")
        
        # Fix 2: Match by amount and date proximity
        print("\n2. Matching by exact amount and date proximity...")
        cur.execute("""
            UPDATE payments 
            SET charter_id = c.charter_id
            FROM charters c
            WHERE payments.reserve_number IS NULL
            AND payments.payment_method = 'bank_transfer'
            AND payments.amount = c.rate
            AND ABS(EXTRACT(DAY FROM (payments.payment_date - c.charter_date))) <= 7
        """)
        amount_fixes = cur.rowcount
        fixes_applied += amount_fixes
        print(f"   Fixed {amount_fixes:,} payments by exact amount + date match")
        
        # Fix 3: Mark refunds/negative amounts appropriately
        print("\n3. Handling negative amounts (refunds)...")
        cur.execute("""
            UPDATE payments 
            SET notes = COALESCE(notes, '') || ' [REFUND - Manual Review Required]'
            WHERE reserve_number IS NULL 
            AND payment_method = 'bank_transfer'
            AND amount < 0
            AND notes NOT LIKE '%REFUND%'
        """)
        refund_fixes = cur.rowcount
        fixes_applied += refund_fixes
        print(f"   Marked {refund_fixes:,} negative amounts as refunds requiring review")
        
        conn.commit()
        print(f"\n✅ Applied {fixes_applied:,} bank transfer specific fixes")
        return fixes_applied
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error applying bank transfer fixes: {e}")
        return 0
    finally:
        cur.close()
        conn.close()

def analyze_remaining_unmatched():
    """Analyze what's left after applying fixes"""
    
    print("\n📊 Analyzing Remaining Unmatched Payments...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Count by method after fixes
        cur.execute("""
            SELECT payment_method, COUNT(*), SUM(amount)
            FROM payments 
            WHERE reserve_number IS NULL
            GROUP BY payment_method
            ORDER BY COUNT(*) DESC
        """)
        remaining_by_method = cur.fetchall()
        
        print("\n💳 Remaining Unmatched by Method:")
        total_remaining = 0
        for method, count, amount in remaining_by_method:
            method_name = method or "(NULL/Unknown)"
            amount_str = f"${amount:,.2f}" if amount else "$0.00"
            print(f"   {method_name}: {count:,} payments ({amount_str})")
            total_remaining += count
            
        # Analyze age of remaining unmatched
        cur.execute("""
            SELECT 
                CASE 
                    WHEN payment_date >= CURRENT_DATE - INTERVAL '30 days' THEN 'Last 30 days'
                    WHEN payment_date >= CURRENT_DATE - INTERVAL '90 days' THEN '30-90 days'
                    WHEN payment_date >= CURRENT_DATE - INTERVAL '365 days' THEN '3-12 months'
                    ELSE 'Over 1 year'
                END as age_group,
                COUNT(*),
                SUM(amount)
            FROM payments 
            WHERE reserve_number IS NULL
            GROUP BY age_group
            ORDER BY COUNT(*) DESC
        """)
        age_analysis = cur.fetchall()
        
        print("\n📅 Remaining Unmatched by Age:")
        for age_group, count, amount in age_analysis:
            amount_str = f"${amount:,.2f}" if amount else "$0.00"
            print(f"   {age_group}: {count:,} payments ({amount_str})")
            
        print(f"\n📈 Summary: {total_remaining:,} payments still need resolution")
        
        # Show sample of most recent unmatched for manual review
        cur.execute("""
            SELECT payment_id, payment_date, amount, payment_method, notes
            FROM payments 
            WHERE reserve_number IS NULL
            ORDER BY payment_date DESC
            LIMIT 10
        """)
        recent_samples = cur.fetchall()
        
        print("\n🔍 Most Recent Unmatched (for manual review):")
        for payment_id, payment_date, amount, method, notes in recent_samples:
            method_str = method or "Unknown"
            notes_str = (notes[:60] + "...") if notes and len(notes) > 60 else (notes or "")
            print(f"   ID {payment_id}: {payment_date} | ${amount:,.2f} | {method_str}")
            print(f"      {notes_str}")
            
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    # Analyze patterns first
    patterns = analyze_bank_transfer_patterns()
    
    # Apply specific fixes
    fixes = apply_bank_transfer_fixes()
    
    # Analyze what remains
    analyze_remaining_unmatched()
    
    print("\n✅ Bank transfer analysis complete!")
    print("💡 Next steps:")
    print("   1. Review manual matching opportunities for recent unmatched payments")
    print("   2. Consider marking older unmatched payments as cash after verification")
    print("   3. Implement process for future payment-charter linking during data entry")