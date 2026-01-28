#!/usr/bin/env python3
"""
Improve Payment-Charter Linkage - Priority 2 Issue Resolution
Links unmatched payments to charters using reserve_number matching.
This addresses the remaining 40-75% payment linkage gaps.
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

def analyze_payment_linkage_issue(cur):
    """Analyze payment-charter linkage gaps"""
    print("🔍 ANALYZING PAYMENT LINKAGE GAPS")
    print("=" * 50)
    
    # Current linkage status
    cur.execute("""
        SELECT 
            COUNT(*) as total_payments,
            COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) as payments_with_charter_id,
            COUNT(CASE WHEN charter_id IS NULL AND reserve_number IS NOT NULL THEN 1 END) as unlinked_with_reserve,
            SUM(COALESCE(amount, 0)) as total_payment_amount,
            SUM(CASE WHEN charter_id IS NOT NULL THEN amount ELSE 0 END) as linked_payment_amount,
            SUM(CASE WHEN charter_id IS NULL AND reserve_number IS NOT NULL THEN amount ELSE 0 END) as unlinked_reserve_amount
        FROM payments 
        WHERE payment_date BETWEEN '2012-01-01' AND '2014-12-31'
    """)
    
    payment_status = cur.fetchone()
    
    # Potential matches via reserve_number
    cur.execute("""
        SELECT 
            COUNT(DISTINCT p.payment_id) as matchable_payments,
            COUNT(DISTINCT c.charter_id) as matching_charters,
            SUM(p.amount) as matchable_amount
        FROM payments p
        INNER JOIN charters c ON p.reserve_number = c.reserve_number
        WHERE p.payment_date BETWEEN '2012-01-01' AND '2014-12-31'
        AND p.reserve_number IS NULL
        AND p.reserve_number IS NOT NULL
        AND c.reserve_number IS NOT NULL
    """)
    
    potential_matches = cur.fetchone()
    
    print(f"Payment Linkage Status:")
    print(f"  Total Payments: {payment_status[0]:,}")
    print(f"  Linked to Charters: {payment_status[1]:,} ({payment_status[1]/payment_status[0]*100:.1f}%)")
    print(f"  Unlinked with Reserve Numbers: {payment_status[2]:,}")
    print(f"  Total Payment Amount: ${payment_status[3]:,.2f}")
    print(f"  Linked Payment Amount: ${payment_status[4]:,.2f}")
    print(f"  Unlinked Reserve Amount: ${payment_status[5]:,.2f}")
    
    print(f"Potential Reserve Number Matches:")
    print(f"  Matchable Payments: {potential_matches[0] or 0:,}")
    print(f"  Matching Charters: {potential_matches[1] or 0:,}")
    print(f"  Matchable Amount: ${float(potential_matches[2]) if potential_matches[2] else 0:,.2f}")
    
    return payment_status, potential_matches

def create_payment_linkage_fixes(cur, dry_run=True):
    """Create fixes for payment-charter linkage using reserve numbers"""
    print(f"\n🔧 PAYMENT LINKAGE FIX")
    print("=" * 40)
    
    # Strategy 1: Link payments to charters via reserve_number where charter_id is NULL
    linkage_sql = """
        UPDATE payments 
        SET charter_id = charter_lookup.charter_id
        FROM (
            SELECT DISTINCT
                c.charter_id,
                c.reserve_number
            FROM charters c
            WHERE c.charter_date BETWEEN '2012-01-01' AND '2014-12-31'
            AND c.reserve_number IS NOT NULL
        ) charter_lookup
        WHERE payments.reserve_number = charter_lookup.reserve_number
        AND payments.charter_id IS NULL
        AND payments.payment_date BETWEEN '2012-01-01' AND '2014-12-31'
        AND payments.reserve_number IS NOT NULL
    """
    
    if dry_run:
        # Preview what would be linked
        preview_sql = """
            SELECT 
                p.payment_id,
                p.reserve_number,
                p.amount,
                p.payment_date,
                c.charter_id,
                c.charter_date,
                c.total_amount_due
            FROM payments p
            INNER JOIN charters c ON p.reserve_number = c.reserve_number
            WHERE p.reserve_number IS NULL
            AND p.payment_date BETWEEN '2012-01-01' AND '2014-12-31'
            AND p.reserve_number IS NOT NULL
            AND c.charter_date BETWEEN '2012-01-01' AND '2014-12-31'
            ORDER BY p.amount DESC
            LIMIT 20
        """
        
        cur.execute(preview_sql)
        results = cur.fetchall()
        
        print("Preview of Payment-Charter Links (Top 20 by amount):")
        print("Payment ID | Reserve | Amount    | Pay Date   | Charter ID | Charter Date | Charter Amount")
        print("-" * 90)
        
        for row in results:
            pid, reserve, amount, pay_date, cid, charter_date, charter_amount = row
            print(f"{pid:10} | {reserve:7} | ${float(amount):8.2f} | {pay_date} | {cid:10} | {charter_date}    | ${float(charter_amount or 0):8.2f}")
        
        # Get total impact
        cur.execute("""
            SELECT 
                COUNT(DISTINCT p.payment_id) as payments_to_link,
                COUNT(DISTINCT c.charter_id) as charters_to_link,
                SUM(p.amount) as total_linkable_amount
            FROM payments p
            INNER JOIN charters c ON p.reserve_number = c.reserve_number
            WHERE p.reserve_number IS NULL
            AND p.payment_date BETWEEN '2012-01-01' AND '2014-12-31'
            AND p.reserve_number IS NOT NULL
            AND c.charter_date BETWEEN '2012-01-01' AND '2014-12-31'
        """)
        
        impact = cur.fetchone()
        
        print(f"\n📊 LINKAGE IMPACT:")
        print(f"Payments to Link: {impact[0] or 0:,}")
        print(f"Charters to Link: {impact[1] or 0:,}")
        print(f"Total Linkable Amount: ${float(impact[2]) if impact[2] else 0:,.2f}")
        
        return linkage_sql, impact
    
    else:
        # Execute the linkage update
        cur.execute(linkage_sql)
        updated_count = cur.rowcount
        print(f"[OK] Linked {updated_count:,} payments to charters")
        return linkage_sql, updated_count

def update_charter_revenue_after_linkage(cur, dry_run=True):
    """Update charter revenue totals after linking more payments"""
    print(f"\n🔧 UPDATING CHARTER REVENUE TOTALS")
    print("=" * 45)
    
    # Update total_amount_due with new payment links
    update_sql = """
        UPDATE charters 
        SET total_amount_due = COALESCE(payment_totals.payment_sum, charters.total_amount_due)
        FROM (
            SELECT 
                charter_id,
                SUM(amount) as payment_sum
            FROM payments 
            WHERE charter_id IS NOT NULL
            AND amount > 0
            GROUP BY charter_id
        ) payment_totals
        WHERE charters.charter_id = payment_totals.charter_id
        AND charters.charter_date BETWEEN '2012-01-01' AND '2014-12-31'
        AND payment_totals.payment_sum > COALESCE(charters.total_amount_due, 0)
    """
    
    if dry_run:
        # Show what would be updated
        cur.execute("""
            SELECT 
                c.charter_id,
                c.reserve_number,
                c.total_amount_due as current_revenue,
                payment_totals.payment_sum as new_revenue,
                (payment_totals.payment_sum - COALESCE(c.total_amount_due, 0)) as revenue_increase
            FROM charters c
            INNER JOIN (
                SELECT 
                    charter_id,
                    SUM(amount) as payment_sum
                FROM payments 
                WHERE charter_id IS NOT NULL
                AND amount > 0
                GROUP BY charter_id
            ) payment_totals ON c.charter_id = payment_totals.charter_id
            WHERE c.charter_date BETWEEN '2012-01-01' AND '2014-12-31'
            AND payment_totals.payment_sum > COALESCE(c.total_amount_due, 0)
            ORDER BY (payment_totals.payment_sum - COALESCE(c.total_amount_due, 0)) DESC
            LIMIT 15
        """)
        
        results = cur.fetchall()
        
        print("Revenue Updates After Payment Linking (Top 15):")
        print("Charter ID | Reserve | Current   | New       | Increase")
        print("-" * 60)
        
        for row in results:
            cid, reserve, current, new_rev, increase = row
            print(f"{cid:10} | {reserve or 'None':7} | ${float(current or 0):8.2f} | ${float(new_rev):8.2f} | ${float(increase):8.2f}")
        
        # Total impact
        cur.execute("""
            SELECT 
                COUNT(*) as charters_to_update,
                SUM(payment_totals.payment_sum - COALESCE(c.total_amount_due, 0)) as total_revenue_increase
            FROM charters c
            INNER JOIN (
                SELECT 
                    charter_id,
                    SUM(amount) as payment_sum
                FROM payments 
                WHERE charter_id IS NOT NULL
                AND amount > 0
                GROUP BY charter_id
            ) payment_totals ON c.charter_id = payment_totals.charter_id
            WHERE c.charter_date BETWEEN '2012-01-01' AND '2014-12-31'
            AND payment_totals.payment_sum > COALESCE(c.total_amount_due, 0)
        """)
        
        impact = cur.fetchone()
        
        print(f"\n📊 REVENUE UPDATE IMPACT:")
        print(f"Charters to Update: {impact[0]:,}")
        print(f"Total Revenue Increase: ${impact[1]:,.2f}")
        
        return update_sql, impact
    
    else:
        cur.execute(update_sql)
        updated_count = cur.rowcount
        print(f"[OK] Updated revenue for {updated_count:,} charters")
        return update_sql, updated_count

def main():
    """Main function to improve payment-charter linkage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Improve Payment-Charter Linkage')
    parser.add_argument('--apply', action='store_true', help='Apply the fixes (default is dry-run)')
    
    args = parser.parse_args()
    
    print("🔧 PAYMENT-CHARTER LINKAGE IMPROVEMENT")
    print("=" * 50)
    print("Addressing: Payment linkage gaps (40-75% currently linked)")
    print("Mode:", "APPLY CHANGES" if args.apply else "DRY RUN (preview only)")
    print("=" * 50)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Analyze current linkage gaps
        payment_status, potential_matches = analyze_payment_linkage_issue(cur)
        
        # Create and show/apply payment linkage fixes
        if args.apply:
            print(f"\n[WARN]  APPLYING PAYMENT LINKAGE FIXES...")
            linkage_sql, linkage_result = create_payment_linkage_fixes(cur, dry_run=False)
            
            print(f"\n[WARN]  UPDATING CHARTER REVENUE TOTALS...")
            revenue_sql, revenue_result = update_charter_revenue_after_linkage(cur, dry_run=False)
            
            conn.commit()
            print(f"\n[OK] PAYMENT LINKAGE FIX COMPLETE")
            print(f"   - Linked {linkage_result} payments to charters")
            print(f"   - Updated revenue for {revenue_result} charters")
        else:
            print(f"\n👀 DRY RUN - Showing proposed changes...")
            linkage_sql, linkage_impact = create_payment_linkage_fixes(cur, dry_run=True)
            revenue_sql, revenue_impact = update_charter_revenue_after_linkage(cur, dry_run=True)
            
            print(f"\n📋 To apply these changes, run:")
            print(f"python {__file__} --apply")
        
    except Exception as e:
        print(f"[FAIL] ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
        
    finally:
        cur.close()
        conn.close()
    
    return True

if __name__ == "__main__":
    main()