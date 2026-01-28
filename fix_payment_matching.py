#!/usr/bin/env python3
"""
Payment-Charter Matching Analysis and Resolution Script
Ensures all payments are either matched to charters or properly marked as cash
"""

import sys
import os
sys.path.insert(0, os.getcwd())

from api import get_db_connection
import json
from datetime import datetime

def analyze_payment_matching():
    """Analyze current payment matching status"""
    
    print("🔍 Analyzing Payment-Charter Matching Status...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Overall statistics
        print("\n📊 Overall Payment Statistics:")
        cur.execute("SELECT COUNT(*) FROM payments")
        total_payments = cur.fetchone()[0]
        print(f"   Total payments in system: {total_payments:,}")
        
        cur.execute("SELECT COUNT(*) FROM payments WHERE reserve_number IS NOT NULL")
        matched_payments = cur.fetchone()[0]
        print(f"   Matched to charters: {matched_payments:,}")
        
        cur.execute("SELECT COUNT(*) FROM payments WHERE reserve_number IS NULL")
        unmatched_payments = cur.fetchone()[0]
        print(f"   Unmatched payments: {unmatched_payments:,}")
        
        match_percentage = (matched_payments / total_payments) * 100 if total_payments > 0 else 0
        print(f"   Match percentage: {match_percentage:.1f}%")
        
        # Unmatched payments by method
        print("\n💳 Unmatched Payments by Method:")
        cur.execute("""
            SELECT payment_method, COUNT(*), SUM(amount) 
            FROM payments 
            WHERE reserve_number IS NULL 
            GROUP BY payment_method 
            ORDER BY COUNT(*) DESC
        """)
        unmatched_by_method = cur.fetchall()
        
        for method, count, total_amount in unmatched_by_method:
            method_name = method or "(NULL/Unknown)"
            amount_str = f"${total_amount:,.2f}" if total_amount else "$0.00"
            print(f"   {method_name}: {count:,} payments ({amount_str})")
        
        # Check for potential matches by reserve number
        print("\n🔗 Checking for Potential Matches by Reserve Number:")
        cur.execute("""
            SELECT COUNT(*) 
            FROM payments p
            LEFT JOIN charters c ON p.reserve_number = c.reserve_number
            WHERE p.reserve_number IS NULL 
            AND p.reserve_number IS NOT NULL 
            AND c.charter_id IS NOT NULL
        """)
        potential_reserve_matches = cur.fetchone()[0]
        print(f"   Payments matchable by reserve number: {potential_reserve_matches:,}")
        
        # Check for potential matches by account number
        cur.execute("""
            SELECT COUNT(*) 
            FROM payments p
            LEFT JOIN charters c ON p.account_number = c.account_number
            WHERE p.reserve_number IS NULL 
            AND p.account_number IS NOT NULL 
            AND c.charter_id IS NOT NULL
        """)
        potential_account_matches = cur.fetchone()[0]
        print(f"   Payments matchable by account number: {potential_account_matches:,}")
        
        # Recent unmatched payments (potential data entry issues)
        print("\n📅 Recent Unmatched Payments (Last 30 days):")
        cur.execute("""
            SELECT COUNT(*), SUM(amount)
            FROM payments 
            WHERE reserve_number IS NULL 
            AND payment_date >= CURRENT_DATE - INTERVAL '30 days'
        """)
        recent_unmatched = cur.fetchone()
        if recent_unmatched and recent_unmatched[0]:
            count, amount = recent_unmatched
            amount_str = f"${amount:,.2f}" if amount else "$0.00"
            print(f"   Recent unmatched: {count:,} payments ({amount_str})")
        else:
            print("   No recent unmatched payments")
        
        # Cash vs non-cash breakdown
        print("\n💵 Cash vs Non-Cash Analysis:")
        cur.execute("""
            SELECT 
                CASE 
                    WHEN LOWER(payment_method) IN ('cash', 'cash payment', 'cash deposit') THEN 'Cash'
                    ELSE 'Non-Cash'
                END as payment_type,
                COUNT(*),
                SUM(amount)
            FROM payments 
            WHERE reserve_number IS NULL
            GROUP BY payment_type
        """)
        cash_breakdown = cur.fetchall()
        
        for payment_type, count, total_amount in cash_breakdown:
            amount_str = f"${total_amount:,.2f}" if total_amount else "$0.00"
            print(f"   {payment_type} unmatched: {count:,} payments ({amount_str})")
            
        return {
            'total_payments': total_payments,
            'matched_payments': matched_payments,
            'unmatched_payments': unmatched_payments,
            'match_percentage': match_percentage,
            'potential_reserve_matches': potential_reserve_matches,
            'potential_account_matches': potential_account_matches
        }
        
    finally:
        cur.close()
        conn.close()

def fix_payment_matching():
    """Attempt to fix payment matching issues"""
    
    print("\n🔧 Fixing Payment-Charter Matching...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        fixes_applied = 0
        
        # Fix 1: Match by reserve number
        print("\n1. Matching payments by reserve number...")
        cur.execute("""
            UPDATE payments 
            SET charter_id = c.charter_id 
            FROM charters c 
            WHERE payments.reserve_number IS NULL 
            AND payments.reserve_number IS NOT NULL 
            AND payments.reserve_number = c.reserve_number
        """)
        reserve_fixes = cur.rowcount
        fixes_applied += reserve_fixes
        print(f"   Fixed {reserve_fixes:,} payments by reserve number")
        
        # Fix 2: Match by account number and date proximity
        print("\n2. Matching payments by account number and date...")
        cur.execute("""
            UPDATE payments 
            SET charter_id = c.charter_id 
            FROM charters c 
            WHERE payments.reserve_number IS NULL 
            AND payments.account_number IS NOT NULL 
            AND payments.account_number = c.account_number
            AND ABS(EXTRACT(DAY FROM (payments.payment_date - c.charter_date))) <= 30
        """)
        account_fixes = cur.rowcount
        fixes_applied += account_fixes
        print(f"   Fixed {account_fixes:,} payments by account number + date proximity")
        
        # Fix 3: Mark obvious cash payments from notes/descriptions
        print("\n3. Marking obvious cash payments...")
        cur.execute("""
            UPDATE payments 
            SET payment_method = 'cash'
            WHERE reserve_number IS NULL 
            AND (
                LOWER(COALESCE(payment_method, '')) LIKE '%cash%' OR
                LOWER(COALESCE(notes, '')) LIKE '%cash%' OR
                LOWER(COALESCE(payment_key, '')) LIKE '%cash%' OR
                LOWER(COALESCE(notes, '')) LIKE '%mr / cash%'
            )
            AND COALESCE(payment_method, '') != 'cash'
        """)
        cash_fixes = cur.rowcount
        fixes_applied += cash_fixes
        print(f"   Marked {cash_fixes:,} payments as cash")
        
        # Fix 4: Match by client_id if available
        print("\n4. Matching payments by client_id...")
        cur.execute("""
            UPDATE payments 
            SET charter_id = c.charter_id 
            FROM charters c 
            WHERE payments.reserve_number IS NULL 
            AND payments.client_id IS NOT NULL 
            AND payments.client_id = c.client_id
            AND ABS(EXTRACT(DAY FROM (payments.payment_date - c.charter_date))) <= 60
        """)
        client_fixes = cur.rowcount
        fixes_applied += client_fixes
        print(f"   Fixed {client_fixes:,} payments by client_id + date proximity")
        
        conn.commit()
        print(f"\n✅ Total fixes applied: {fixes_applied:,}")
        
        return fixes_applied
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error applying fixes: {e}")
        return 0
    finally:
        cur.close()
        conn.close()

def mark_remaining_as_cash():
    """Mark remaining unmatched payments as cash after manual review"""
    
    print("\n💵 Marking Remaining Unmatched Payments as Cash...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get count of remaining unmatched
        cur.execute("""
            SELECT COUNT(*), SUM(amount)
            FROM payments 
            WHERE reserve_number IS NULL 
            AND payment_method != 'cash'
        """)
        remaining = cur.fetchone()
        
        if remaining and remaining[0] > 0:
            count, amount = remaining
            amount_str = f"${amount:,.2f}" if amount else "$0.00"
            print(f"   Remaining unmatched: {count:,} payments ({amount_str})")
            
            # Show sample of what will be marked as cash
            cur.execute("""
                SELECT payment_id, payment_date, amount, payment_method, notes
                FROM payments 
                WHERE reserve_number IS NULL 
                AND payment_method != 'cash'
                ORDER BY payment_date DESC
                LIMIT 10
            """)
            samples = cur.fetchall()
            
            print("\n   Sample of payments to be marked as cash:")
            for payment_id, payment_date, amount, method, notes in samples:
                method_str = method or "Unknown"
                notes_str = (notes[:50] + "...") if notes and len(notes) > 50 else (notes or "")
                print(f"     ID {payment_id}: {payment_date} | ${amount:,.2f} | {method_str} | {notes_str}")
            
            # Confirmation prompt simulation (in real scenario, would ask for confirmation)
            print(f"\n⚠️  This will mark {count:,} payments as 'cash' payments")
            print("   This should only be done after manual review to confirm these are legitimate cash transactions")
            
            # Uncomment the following lines to actually apply the changes:
            # cur.execute("""
            #     UPDATE payments 
            #     SET payment_method = 'cash'
            #     WHERE reserve_number IS NULL 
            #     AND payment_method != 'cash'
            # """)
            # conn.commit()
            # print(f"✅ Marked {cur.rowcount:,} payments as cash")
            
        else:
            print("   No remaining unmatched non-cash payments")
            
    finally:
        cur.close()
        conn.close()

def generate_payment_matching_report():
    """Generate a comprehensive payment matching report"""
    
    print("\n📋 Generating Payment Matching Report...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {},
            'details': {}
        }
        
        # Summary statistics
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN charter_id IS NOT NULL THEN 1 ELSE 0 END) as matched,
                SUM(CASE WHEN charter_id IS NULL AND payment_method = 'cash' THEN 1 ELSE 0 END) as cash,
                SUM(CASE WHEN charter_id IS NULL AND payment_method != 'cash' THEN 1 ELSE 0 END) as unmatched,
                SUM(amount) as total_amount,
                SUM(CASE WHEN charter_id IS NOT NULL THEN amount ELSE 0 END) as matched_amount,
                SUM(CASE WHEN charter_id IS NULL THEN amount ELSE 0 END) as unmatched_amount
            FROM payments
        """)
        
        summary = cur.fetchone()
        report['summary'] = {
            'total_payments': summary[0],
            'matched_payments': summary[1],
            'cash_payments': summary[2],
            'unmatched_payments': summary[3],
            'total_amount': float(summary[4]) if summary[4] else 0,
            'matched_amount': float(summary[5]) if summary[5] else 0,
            'unmatched_amount': float(summary[6]) if summary[6] else 0,
            'match_percentage': (summary[1] / summary[0] * 100) if summary[0] > 0 else 0
        }
        
        print("📊 Final Payment Matching Summary:")
        print(f"   Total payments: {report['summary']['total_payments']:,}")
        print(f"   ✅ Matched to charters: {report['summary']['matched_payments']:,}")
        print(f"   💵 Cash payments: {report['summary']['cash_payments']:,}")
        print(f"   ❌ Still unmatched: {report['summary']['unmatched_payments']:,}")
        print(f"   📈 Overall match rate: {report['summary']['match_percentage']:.1f}%")
        
        print(f"\n💰 Financial Summary:")
        print(f"   Total amount: ${report['summary']['total_amount']:,.2f}")
        print(f"   Matched amount: ${report['summary']['matched_amount']:,.2f}")
        print(f"   Unmatched amount: ${report['summary']['unmatched_amount']:,.2f}")
        
        # Save report to file
        with open('payment_matching_report.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n📄 Report saved to: payment_matching_report.json")
        
        return report
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    # Step 1: Analyze current state
    analysis = analyze_payment_matching()
    
    # Step 2: Apply automated fixes
    if analysis['unmatched_payments'] > 0:
        fixes = fix_payment_matching()
        
        # Step 3: Re-analyze after fixes
        print(f"\n🔄 Re-analyzing after applying {fixes:,} fixes...")
        analysis = analyze_payment_matching()
    
    # Step 4: Handle remaining unmatched (requires manual review)
    if analysis['unmatched_payments'] > 0:
        mark_remaining_as_cash()
    
    # Step 5: Generate final report
    generate_payment_matching_report()
    
    print("\n✅ Payment-Charter matching analysis complete!")