#!/usr/bin/env python3
"""
Simple Payment Status Summary
Quick analysis of current payment matching status
"""

import sys
import os
sys.path.insert(0, os.getcwd())

from api import get_db_connection

def payment_status_summary():
    """Generate simple payment status summary"""
    
    print("📋 PAYMENT-CHARTER MATCHING SUMMARY")
    print("=" * 50)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Basic statistics
        cur.execute("SELECT COUNT(*) FROM payments")
        total_payments = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM payments WHERE reserve_number IS NOT NULL")
        matched_payments = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM payments WHERE reserve_number IS NULL")
        unmatched_payments = cur.fetchone()[0]
        
        cur.execute("SELECT SUM(amount) FROM payments")
        total_amount = cur.fetchone()[0] or 0
        
        cur.execute("SELECT SUM(amount) FROM payments WHERE reserve_number IS NOT NULL")
        matched_amount = cur.fetchone()[0] or 0
        
        cur.execute("SELECT SUM(amount) FROM payments WHERE reserve_number IS NULL")
        unmatched_amount = cur.fetchone()[0] or 0
        
        match_percentage = (matched_payments / total_payments * 100) if total_payments > 0 else 0
        
        print(f"\n📊 OVERALL STATISTICS:")
        print(f"   Total payments: {total_payments:,}")
        print(f"   ✅ Matched to charters: {matched_payments:,} ({match_percentage:.1f}%)")
        print(f"   ❌ Unmatched: {unmatched_payments:,}")
        
        print(f"\n💰 FINANCIAL SUMMARY:")
        print(f"   Total amount: ${total_amount:,.2f}")
        print(f"   Matched amount: ${matched_amount:,.2f}")
        print(f"   Unmatched amount: ${unmatched_amount:,.2f}")
        
        # Unmatched by payment method
        print(f"\n💳 UNMATCHED BY METHOD:")
        cur.execute("""
            SELECT 
                COALESCE(payment_method, 'Unknown') as method,
                COUNT(*) as count,
                SUM(amount) as amount
            FROM payments 
            WHERE reserve_number IS NULL
            GROUP BY payment_method
            ORDER BY COUNT(*) DESC
        """)
        
        for method, count, amount in cur.fetchall():
            amount_str = f"${amount:,.2f}" if amount else "$0.00"
            print(f"   {method}: {count:,} payments ({amount_str})")
        
        # Recent unmatched (last 30 days)
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
            print(f"\n🚨 RECENT UNMATCHED (30 days): {count:,} payments ({amount_str})")
        
        # Cash payments check
        cur.execute("""
            SELECT COUNT(*), SUM(amount)
            FROM payments 
            WHERE LOWER(COALESCE(payment_method, '')) = 'cash'
        """)
        cash_stats = cur.fetchone()
        if cash_stats and cash_stats[0]:
            count, amount = cash_stats
            amount_str = f"${amount:,.2f}" if amount else "$0.00"
            print(f"\n💵 CASH PAYMENTS: {count:,} payments ({amount_str})")
        else:
            print(f"\n💵 CASH PAYMENTS: None currently marked as cash")
        
        # Assessment
        print(f"\n✅ ASSESSMENT:")
        if match_percentage >= 95:
            status = "🟢 EXCELLENT"
        elif match_percentage >= 80:
            status = "🟡 GOOD"
        elif match_percentage >= 60:
            status = "🟠 FAIR"
        else:
            status = "🔴 NEEDS IMPROVEMENT"
        
        print(f"   Status: {status} ({match_percentage:.1f}% matched)")
        
        if unmatched_payments > 0:
            print(f"\n💡 NEXT STEPS:")
            print(f"   1. Review {unmatched_payments:,} unmatched payments")
            print(f"   2. Check for additional matching patterns")
            print(f"   3. Mark legitimate cash payments as 'cash'")
            print(f"   4. Implement process improvements for future payments")
        
        return {
            'total_payments': total_payments,
            'matched_payments': matched_payments,
            'unmatched_payments': unmatched_payments,
            'match_percentage': match_percentage,
            'total_amount': float(total_amount),
            'matched_amount': float(matched_amount),
            'unmatched_amount': float(unmatched_amount)
        }
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    summary = payment_status_summary()
    print(f"\n" + "=" * 50)
    print("📋 SUMMARY COMPLETE")
    print("=" * 50)