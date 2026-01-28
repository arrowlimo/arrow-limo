#!/usr/bin/env python3
"""
Final Payment Matching Status Report
Comprehensive analysis of payment-charter matching after all automated fixes
"""

import sys
import os
sys.path.insert(0, os.getcwd())

from api import get_db_connection
import json
from datetime import datetime

def generate_final_status_report():
    """Generate comprehensive final status report"""
    
    print("📋 PAYMENT-CHARTER MATCHING FINAL STATUS REPORT")
    print("=" * 60)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Overall statistics after all fixes
        cur.execute("""
            SELECT 
                COUNT(*) as total_payments,
                SUM(CASE WHEN charter_id IS NOT NULL THEN 1 ELSE 0 END) as matched_to_charters,
                SUM(CASE WHEN charter_id IS NULL AND LOWER(COALESCE(payment_method, '')) = 'cash' THEN 1 ELSE 0 END) as cash_payments,
                SUM(CASE WHEN charter_id IS NULL AND LOWER(COALESCE(payment_method, '')) != 'cash' THEN 1 ELSE 0 END) as unmatched_non_cash,
                SUM(amount) as total_amount,
                SUM(CASE WHEN charter_id IS NOT NULL THEN amount ELSE 0 END) as matched_amount,
                SUM(CASE WHEN charter_id IS NULL THEN amount ELSE 0 END) as unmatched_amount
            FROM payments
        """)
        
        stats = cur.fetchone()
        total_payments = stats[0]
        matched_to_charters = stats[1]
        cash_payments = stats[2]
        unmatched_non_cash = stats[3]
        total_amount = float(stats[4]) if stats[4] else 0
        matched_amount = float(stats[5]) if stats[5] else 0
        unmatched_amount = float(stats[6]) if stats[6] else 0
        
        properly_handled = matched_to_charters + cash_payments
        properly_handled_percentage = (properly_handled / total_payments * 100) if total_payments > 0 else 0
        match_percentage = (matched_to_charters / total_payments * 100) if total_payments > 0 else 0
        
        print(f"\n📊 OVERALL SUMMARY:")
        print(f"   Total payments in system: {total_payments:,}")
        print(f"   ✅ Matched to charters: {matched_to_charters:,} ({match_percentage:.1f}%)")
        print(f"   💵 Cash payments: {cash_payments:,}")
        print(f"   ❌ Unmatched non-cash: {unmatched_non_cash:,}")
        print(f"   📈 Properly handled: {properly_handled:,} ({properly_handled_percentage:.1f}%)")
        
        print(f"\n💰 FINANCIAL SUMMARY:")
        print(f"   Total payment amount: ${total_amount:,.2f}")
        print(f"   Matched amount: ${matched_amount:,.2f}")
        print(f"   Unmatched amount: ${unmatched_amount:,.2f}")
        
        # Breakdown of remaining unmatched by method
        print(f"\n🔍 REMAINING UNMATCHED BREAKDOWN:")
        cur.execute("""
            SELECT 
                COALESCE(payment_method, 'Unknown') as method,
                COUNT(*) as count,
                SUM(amount) as total_amount,
                MIN(payment_date) as earliest_date,
                MAX(payment_date) as latest_date
            FROM payments 
            WHERE reserve_number IS NULL 
            AND LOWER(COALESCE(payment_method, '')) != 'cash'
            GROUP BY payment_method
            ORDER BY COUNT(*) DESC
        """)
        
        unmatched_methods = cur.fetchall()
        for method, count, amount, earliest, latest in unmatched_methods:
            amount_str = f"${amount:,.2f}" if amount else "$0.00"
            date_range = f"{earliest} to {latest}" if earliest and latest else "Unknown dates"
            print(f"   {method}: {count:,} payments ({amount_str}) | {date_range}")
        
        # Age analysis of unmatched payments
        print(f"\n📅 UNMATCHED PAYMENTS BY AGE:")
        cur.execute("""
            SELECT 
                CASE 
                    WHEN payment_date >= CURRENT_DATE - INTERVAL '30 days' THEN 'Last 30 days'
                    WHEN payment_date >= CURRENT_DATE - INTERVAL '90 days' THEN '30-90 days ago'
                    WHEN payment_date >= CURRENT_DATE - INTERVAL '365 days' THEN '3-12 months ago'
                    WHEN payment_date >= CURRENT_DATE - INTERVAL '1095 days' THEN '1-3 years ago'
                    ELSE 'Over 3 years ago'
                END as age_group,
                COUNT(*) as count,
                SUM(amount) as total_amount
            FROM payments 
            WHERE reserve_number IS NULL 
            AND LOWER(COALESCE(payment_method, '')) != 'cash'
            GROUP BY 
                CASE 
                    WHEN payment_date >= CURRENT_DATE - INTERVAL '30 days' THEN 'Last 30 days'
                    WHEN payment_date >= CURRENT_DATE - INTERVAL '90 days' THEN '30-90 days ago'
                    WHEN payment_date >= CURRENT_DATE - INTERVAL '365 days' THEN '3-12 months ago'
                    WHEN payment_date >= CURRENT_DATE - INTERVAL '1095 days' THEN '1-3 years ago'
                    ELSE 'Over 3 years ago'
                END
            ORDER BY 
                CASE 
                    WHEN payment_date >= CURRENT_DATE - INTERVAL '30 days' THEN 1
                    WHEN payment_date >= CURRENT_DATE - INTERVAL '90 days' THEN 2
                    WHEN payment_date >= CURRENT_DATE - INTERVAL '365 days' THEN 3
                    WHEN payment_date >= CURRENT_DATE - INTERVAL '1095 days' THEN 4
                    ELSE 5
                END
        """)
        
        age_groups = cur.fetchall()
        for age_group, count, amount in age_groups:
            amount_str = f"${amount:,.2f}" if amount else "$0.00"
            print(f"   {age_group}: {count:,} payments ({amount_str})")
        
        # Recent unmatched that need attention
        print(f"\n🚨 RECENT UNMATCHED REQUIRING ATTENTION:")
        cur.execute("""
            SELECT payment_id, payment_date, amount, payment_method, notes
            FROM payments 
            WHERE reserve_number IS NULL 
            AND payment_date >= CURRENT_DATE - INTERVAL '30 days'
            AND LOWER(COALESCE(payment_method, '')) != 'cash'
            ORDER BY payment_date DESC, amount DESC
            LIMIT 15
        """)
        
        recent_unmatched = cur.fetchall()
        if recent_unmatched:
            print(f"   Found {len(recent_unmatched)} recent unmatched payments:")
            for payment_id, payment_date, amount, method, notes in recent_unmatched:
                method_str = method or "Unknown"
                notes_str = (notes[:50] + "...") if notes and len(notes) > 50 else (notes or "No notes")
                print(f"     ID {payment_id}: {payment_date} | ${amount:,.2f} | {method_str}")
                print(f"       Notes: {notes_str}")
        else:
            print("   ✅ No recent unmatched payments!")
        
        # Cash payment analysis
        print(f"\n💵 CASH PAYMENT ANALYSIS:")
        cur.execute("""
            SELECT COUNT(*), SUM(amount), MIN(payment_date), MAX(payment_date)
            FROM payments 
            WHERE LOWER(COALESCE(payment_method, '')) = 'cash'
        """)
        
        cash_stats = cur.fetchone()
        if cash_stats and cash_stats[0] > 0:
            cash_count, cash_amount, cash_earliest, cash_latest = cash_stats
            print(f"   Total cash payments: {cash_count:,}")
            print(f"   Cash payment amount: ${cash_amount:,.2f}")
            print(f"   Date range: {cash_earliest} to {cash_latest}")
        else:
            print("   ⚠️  No payments marked as cash")
        
        # Generate recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        
        # Recent unmatched need review
        recent_count = sum(1 for age_group, count, amount in age_groups if age_group == 'Last 30 days')
        if recent_count > 0:
            print(f"   🔍 PRIORITY: Review {recent_count:,} recent unmatched payments manually")
            print(f"      These may be legitimate charter payments that need manual linking")
        
        # Old unmatched could be cash
        old_count = sum(count for age_group, count, amount in age_groups if 'years ago' in age_group)
        if old_count > 0:
            print(f"   💵 CONSIDER: Mark {old_count:,} payments over 1 year old as cash after verification")
            print(f"      Historical unmatched payments are likely cash transactions")
        
        # Bank transfer patterns
        bank_transfer_count = next((count for method, count, amount, earliest, latest in unmatched_methods if method == 'bank_transfer'), 0)
        if bank_transfer_count > 0:
            print(f"   🏦 INVESTIGATE: {bank_transfer_count:,} unmatched bank transfers")
            print(f"      Check for additional patterns in LMS deposit notes")
        
        # Check payments analysis
        check_count = next((count for method, count, amount, earliest, latest in unmatched_methods if method == 'check'), 0)
        if check_count > 0:
            print(f"   🏦 REVIEW: {check_count:,} unmatched check payments")
            print(f"      Some checks may have negative amounts (refunds) requiring special handling")
        
        print(f"\n✅ OVERALL ASSESSMENT:")
        if properly_handled_percentage >= 95:
            print(f"   🟢 EXCELLENT: {properly_handled_percentage:.1f}% of payments are properly handled")
        elif properly_handled_percentage >= 85:
            print(f"   🟡 GOOD: {properly_handled_percentage:.1f}% of payments are properly handled")
        else:
            print(f"   🔴 NEEDS WORK: Only {properly_handled_percentage:.1f}% of payments are properly handled")
        
        if unmatched_non_cash < 1000:
            print(f"   🎯 Focus on resolving remaining {unmatched_non_cash:,} unmatched payments")
        else:
            print(f"   📋 Systematic review needed for {unmatched_non_cash:,} unmatched payments")
        
        # Save detailed report
        report_data = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_payments': total_payments,
                'matched_to_charters': matched_to_charters,
                'cash_payments': cash_payments,
                'unmatched_non_cash': unmatched_non_cash,
                'properly_handled_percentage': properly_handled_percentage,
                'match_percentage': match_percentage,
                'total_amount': total_amount,
                'matched_amount': matched_amount,
                'unmatched_amount': unmatched_amount
            },
            'unmatched_by_method': [
                {
                    'method': method,
                    'count': count,
                    'amount': float(amount) if amount else 0,
                    'earliest_date': earliest.isoformat() if earliest else None,
                    'latest_date': latest.isoformat() if latest else None
                }
                for method, count, amount, earliest, latest in unmatched_methods
            ],
            'unmatched_by_age': [
                {
                    'age_group': age_group,
                    'count': count,
                    'amount': float(amount) if amount else 0
                }
                for age_group, count, amount in age_groups
            ]
        }
        
        with open('final_payment_status_report.json', 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        print(f"\n📄 Detailed report saved to: final_payment_status_report.json")
        
        return report_data
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    generate_final_status_report()
    
    print(f"\n" + "=" * 60)
    print("📋 PAYMENT-CHARTER MATCHING STATUS: ANALYSIS COMPLETE")
    print("=" * 60)