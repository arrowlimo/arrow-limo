#!/usr/bin/env python3
"""
Fix Charter Revenue Calculation - Priority 1 Issue Resolution
Updates charter.total_amount_due based on linked payments and rate information.
This addresses the critical $4M+ revenue variance identified in the audit.
"""

import psycopg2
import os
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def analyze_charter_revenue_issue(cur):
    """Analyze the charter revenue calculation problem"""
    print("🔍 ANALYZING CHARTER REVENUE ISSUE")
    print("=" * 50)
    
    # Check charter fields
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            COUNT(CASE WHEN total_amount_due > 0 THEN 1 END) as charters_with_revenue,
            COUNT(CASE WHEN rate > 0 THEN 1 END) as charters_with_rate,
            COUNT(CASE WHEN paid_amount > 0 THEN 1 END) as charters_with_paid_amount,
            SUM(COALESCE(rate, 0)) as total_base_rates,
            SUM(COALESCE(paid_amount, 0)) as total_paid_amounts,
            SUM(COALESCE(total_amount_due, 0)) as total_revenue_field
        FROM charters 
        WHERE charter_date BETWEEN '2012-01-01' AND '2014-12-31'
    """)
    
    charter_analysis = cur.fetchone()
    
    # Check payment totals by charter linkage
    cur.execute("""
        SELECT 
            COUNT(*) as total_payments,
            COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) as payments_with_charter_id,
            SUM(COALESCE(amount, 0)) as total_payment_amount,
            SUM(CASE WHEN charter_id IS NOT NULL THEN amount ELSE 0 END) as payments_linked_to_charters
        FROM payments 
        WHERE payment_date BETWEEN '2012-01-01' AND '2014-12-31'
    """)
    
    payment_analysis = cur.fetchone()
    
    print(f"Charter Analysis:")
    print(f"  Total Charters: {charter_analysis[0]:,}")
    print(f"  Charters with Revenue Field > 0: {charter_analysis[1]:,}")
    print(f"  Charters with Rate > 0: {charter_analysis[2]:,}")
    print(f"  Charters with Paid Amount > 0: {charter_analysis[3]:,}")
    print(f"  Total Base Rates: ${charter_analysis[4]:,.2f}")
    print(f"  Total Paid Amounts: ${charter_analysis[5]:,.2f}")
    print(f"  Total Revenue Field: ${charter_analysis[6]:,.2f}")
    
    print(f"\nPayment Analysis:")
    print(f"  Total Payments: {payment_analysis[0]:,}")
    print(f"  Payments Linked to Charters: {payment_analysis[1]:,}")
    print(f"  Total Payment Amount: ${payment_analysis[2]:,.2f}")
    print(f"  Payments Linked Amount: ${payment_analysis[3]:,.2f}")
    
    return charter_analysis, payment_analysis

def propose_revenue_calculation_fixes(cur):
    """Propose different methods to calculate charter revenue"""
    print(f"\n💡 REVENUE CALCULATION OPTIONS")
    print("=" * 40)
    
    # Option 1: Use payment sums linked by charter_id
    cur.execute("""
        SELECT 
            COUNT(DISTINCT c.charter_id) as charters_with_payments,
            SUM(p.amount) as total_linked_payment_amount
        FROM charters c
        INNER JOIN payments p ON p.charter_id = c.charter_id
        WHERE c.charter_date BETWEEN '2012-01-01' AND '2014-12-31'
    """)
    
    option1 = cur.fetchone()
    
    # Option 2: Use payment sums linked by reserve_number
    cur.execute("""
        SELECT 
            COUNT(DISTINCT c.charter_id) as charters_with_reserve_payments,
            SUM(p.amount) as total_reserve_linked_amount
        FROM charters c
        INNER JOIN payments p ON p.reserve_number = c.reserve_number
        WHERE c.charter_date BETWEEN '2012-01-01' AND '2014-12-31'
        AND c.reserve_number IS NOT NULL 
        AND p.reserve_number IS NOT NULL
    """)
    
    option2 = cur.fetchone()
    
    # Option 3: Use existing paid_amount field
    cur.execute("""
        SELECT 
            COUNT(*) as charters_with_paid_amount,
            SUM(paid_amount) as total_using_paid_amount_field
        FROM charters 
        WHERE charter_date BETWEEN '2012-01-01' AND '2014-12-31'
        AND paid_amount > 0
    """)
    
    option3 = cur.fetchone()
    
    print(f"Option 1 - Charter ID Links:")
    print(f"  Charters: {option1[0]:,}, Amount: ${option1[1]:,.2f}")
    
    print(f"Option 2 - Reserve Number Links:")
    print(f"  Charters: {option2[0]:,}, Amount: ${option2[1]:,.2f}")
    
    print(f"Option 3 - Existing Paid Amount Field:")
    print(f"  Charters: {option3[0]:,}, Amount: ${option3[1]:,.2f}")
    
    return option1, option2, option3

def create_revenue_fix_sql(cur, dry_run=True):
    """Create SQL to fix charter revenue calculation"""
    print(f"\n🔧 GENERATING REVENUE FIX SQL")
    print("=" * 40)
    
    # Strategy: Update total_amount_due with payment sums
    update_sql = """
        UPDATE charters 
        SET total_amount_due = payment_totals.payment_sum
        FROM (
            SELECT 
                charter_id,
                SUM(amount) as payment_sum
            FROM payments 
            WHERE reserve_number IS NOT NULL
            AND amount > 0
            GROUP BY charter_id
        ) payment_totals
        WHERE charters.charter_id = payment_totals.charter_id
        AND charters.charter_date BETWEEN '2012-01-01' AND '2014-12-31'
    """
    
    if dry_run:
        # Show what would be updated
        preview_sql = """
            SELECT 
                c.charter_id,
                c.reserve_number,
                c.charter_date,
                c.total_amount_due as current_revenue,
                payment_totals.payment_sum as proposed_revenue,
                (payment_totals.payment_sum - COALESCE(c.total_amount_due, 0)) as revenue_change
            FROM charters c
            INNER JOIN (
                SELECT 
                    charter_id,
                    SUM(amount) as payment_sum
                FROM payments 
                WHERE reserve_number IS NOT NULL
                AND amount > 0
                GROUP BY charter_id
            ) payment_totals ON c.charter_id = payment_totals.charter_id
            WHERE c.charter_date BETWEEN '2012-01-01' AND '2014-12-31'
            ORDER BY payment_totals.payment_sum DESC
            LIMIT 20
        """
        
        cur.execute(preview_sql)
        results = cur.fetchall()
        
        print("Preview of Revenue Corrections (Top 20 by amount):")
        print("Charter ID | Reserve | Date       | Current | Proposed | Change")
        print("-" * 70)
        
        total_change = 0
        for row in results:
            charter_id, reserve_num, charter_date, current, proposed, change = row
            total_change += float(change) if change else 0
            print(f"{charter_id:10} | {reserve_num or 'None':7} | {charter_date} | ${float(current or 0):8.2f} | ${float(proposed):9.2f} | ${float(change):10.2f}")
        
        # Get total impact
        cur.execute("""
            SELECT 
                COUNT(*) as charters_to_update,
                SUM(payment_totals.payment_sum) as total_new_revenue,
                SUM(COALESCE(c.total_amount_due, 0)) as total_current_revenue,
                SUM(payment_totals.payment_sum - COALESCE(c.total_amount_due, 0)) as total_revenue_increase
            FROM charters c
            INNER JOIN (
                SELECT 
                    charter_id,
                    SUM(amount) as payment_sum
                FROM payments 
                WHERE reserve_number IS NOT NULL
                AND amount > 0
                GROUP BY charter_id
            ) payment_totals ON c.charter_id = payment_totals.charter_id
            WHERE c.charter_date BETWEEN '2012-01-01' AND '2014-12-31'
        """)
        
        impact = cur.fetchone()
        
        print(f"\n📊 TOTAL IMPACT:")
        print(f"Charters to Update: {impact[0]:,}")
        print(f"Total New Revenue: ${impact[1]:,.2f}")
        print(f"Total Current Revenue: ${impact[2]:,.2f}")
        print(f"Total Revenue Increase: ${impact[3]:,.2f}")
        
        return update_sql, impact
    
    else:
        # Execute the update
        cur.execute(update_sql)
        updated_count = cur.rowcount
        print(f"[OK] Updated {updated_count:,} charter records")
        return update_sql, updated_count

def main():
    """Main function to analyze and optionally fix charter revenue"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix Charter Revenue Calculation Issue')
    parser.add_argument('--apply', action='store_true', help='Apply the fixes (default is dry-run)')
    parser.add_argument('--year', type=int, help='Specific year to fix (default: 2012-2014)')
    
    args = parser.parse_args()
    
    print("🔧 CHARTER REVENUE CALCULATION FIX")
    print("=" * 50)
    print("Addressing: $4M+ revenue variance from comprehensive audit")
    print("Mode:", "APPLY CHANGES" if args.apply else "DRY RUN (preview only)")
    print("=" * 50)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Analyze the issue
        charter_analysis, payment_analysis = analyze_charter_revenue_issue(cur)
        
        # Show options
        options = propose_revenue_calculation_fixes(cur)
        
        # Create and show/apply fix
        if args.apply:
            print(f"\n[WARN]  APPLYING REVENUE FIXES...")
            update_sql, result = create_revenue_fix_sql(cur, dry_run=False)
            conn.commit()
            print(f"[OK] REVENUE FIX COMPLETE: {result} records updated")
        else:
            print(f"\n👀 DRY RUN - Showing proposed changes...")
            update_sql, impact = create_revenue_fix_sql(cur, dry_run=True)
            print(f"\n📋 To apply these changes, run:")
            print(f"python {__file__} --apply")
        
    except Exception as e:
        print(f"[FAIL] ERROR: {str(e)}")
        conn.rollback()
        return False
        
    finally:
        cur.close()
        conn.close()
    
    return True

if __name__ == "__main__":
    main()