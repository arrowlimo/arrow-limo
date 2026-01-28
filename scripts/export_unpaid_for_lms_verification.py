#!/usr/bin/env python3
"""
Export unpaid charters for LMS verification.
Creates CSV with 363 unpaid charters for manual verification against legacy LMS Access database.
"""

import os
import sys
import psycopg2
import csv
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def export_unpaid_charters():
    """Export unpaid charters for LMS verification."""
    
    print("📋 EXPORTING UNPAID CHARTERS FOR LMS VERIFICATION")
    print("=" * 70)
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        # Get unpaid charters (using reserve_number join - CRITICAL!)
        cursor.execute("""
            WITH charter_payments AS (
                SELECT 
                    c.charter_id,
                    c.reserve_number,
                    COALESCE(SUM(p.amount), 0) as total_paid
                FROM charters c
                LEFT JOIN payments p ON p.reserve_number = c.reserve_number
                GROUP BY c.charter_id, c.reserve_number
            )
            SELECT 
                c.charter_id,
                c.reserve_number,
                c.charter_date,
                COALESCE(c.client_display_name, '') AS customer_name,
                c.total_amount_due,
                COALESCE(cp.total_paid, 0) as total_paid,
                c.total_amount_due - COALESCE(cp.total_paid, 0) as outstanding,
                c.status,
                c.notes,
                c.created_at,
                c.updated_at
            FROM charters c
            LEFT JOIN charter_payments cp ON c.charter_id = cp.charter_id
            WHERE c.total_amount_due - COALESCE(cp.total_paid, 0) > 0.01
            ORDER BY c.charter_date DESC, c.reserve_number DESC
        """)
        
        rows = cursor.fetchall()
        
        print(f"✅ Found {len(rows):,} unpaid charters\n")
        
        # Create output file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"l:/limo/reports/unpaid_charters_for_lms_check_{timestamp}.csv"
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'charter_id',
                'reserve_number',
                'charter_date',
                'customer_name',
                'total_amount_due',
                'total_paid_almsdata',
                'outstanding',
                'status',
                'notes',
                'created_at',
                'updated_at',
                'lms_charge_amount',  # For manual entry
                'lms_paid_amount',    # For manual entry
                'lms_status',         # For manual entry
                'category',           # For manual entry: A=BadDebt, B=ShouldBeZero, C=Cancelled, D=PaymentMissing, E=Legitimate
                'action_required'     # For manual entry: description of what to do
            ])
            
            # Data rows
            for row in rows:
                writer.writerow(row + ('', '', '', '', ''))  # Add empty columns for manual entry
        
        print(f"✅ Export complete: {output_file}\n")
        
        # Summary statistics
        cursor.execute("""
            WITH charter_payments AS (
                SELECT 
                    c.charter_id,
                    c.reserve_number,
                    COALESCE(SUM(p.amount), 0) as total_paid
                FROM charters c
                LEFT JOIN payments p ON p.reserve_number = c.reserve_number
                GROUP BY c.charter_id, c.reserve_number
            )
            SELECT 
                COUNT(*) as count,
                SUM(c.total_amount_due - COALESCE(cp.total_paid, 0)) as total_outstanding
            FROM charters c
            LEFT JOIN charter_payments cp ON c.charter_id = cp.charter_id
            WHERE c.total_amount_due - COALESCE(cp.total_paid, 0) > 0.01
        """)
        
        count, total = cursor.fetchone()
        
        print("📊 SUMMARY")
        print("-" * 70)
        print(f"Unpaid Charters: {count:,}")
        print(f"Total Outstanding: ${total:,.2f}")
        
        # Breakdown by status
        cursor.execute("""
            WITH charter_payments AS (
                SELECT 
                    c.charter_id,
                    COALESCE(SUM(p.amount), 0) as total_paid
                FROM charters c
                LEFT JOIN payments p ON p.reserve_number = c.reserve_number
                GROUP BY c.charter_id
            )
            SELECT 
                c.status,
                COUNT(*) as count,
                SUM(c.total_amount_due - COALESCE(cp.total_paid, 0)) as total_outstanding
            FROM charters c
            LEFT JOIN charter_payments cp ON c.charter_id = cp.charter_id
            WHERE c.total_amount_due - COALESCE(cp.total_paid, 0) > 0.01
            GROUP BY c.status
            ORDER BY total_outstanding DESC
        """)
        
        print("\nBREAKDOWN BY STATUS:")
        for status, count, outstanding in cursor.fetchall():
            print(f"  {status or 'NULL':<15} {count:>6,} charters   ${outstanding:>12,.2f}")
        
        # Breakdown by year
        cursor.execute("""
            WITH charter_payments AS (
                SELECT 
                    c.charter_id,
                    COALESCE(SUM(p.amount), 0) as total_paid
                FROM charters c
                LEFT JOIN payments p ON p.reserve_number = c.reserve_number
                GROUP BY c.charter_id
            )
            SELECT 
                EXTRACT(YEAR FROM c.charter_date) as year,
                COUNT(*) as count,
                SUM(c.total_amount_due - COALESCE(cp.total_paid, 0)) as total_outstanding
            FROM charters c
            LEFT JOIN charter_payments cp ON c.charter_id = cp.charter_id
            WHERE c.total_amount_due - COALESCE(cp.total_paid, 0) > 0.01
            GROUP BY EXTRACT(YEAR FROM c.charter_date)
            ORDER BY year DESC
        """)
        
        print("\nBREAKDOWN BY YEAR:")
        for year, count, outstanding in cursor.fetchall():
            print(f"  {int(year):<6} {count:>6,} charters   ${outstanding:>12,.2f}")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 70)
        print("✅ NEXT STEP: Open legacy LMS Access database and verify each charter")
        print(f"   File: {output_file}")
        print("\n📋 FOR EACH CHARTER, CHECK:")
        print("   1. Does charge amount match total_amount_due?")
        print("   2. Is it paid in LMS but not in almsdata?")
        print("   3. Is it trade/barter/complimentary (should be $0)?")
        print("   4. Is it cancelled (should be $0)?")
        print("   5. Is it bad debt (uncollectable)?")
        print("\n📝 CATEGORIES TO ASSIGN:")
        print("   A = Bad Debt (write-off)")
        print("   B = Should Be Zero (trade/comp/promo)")
        print("   C = Cancelled (not marked)")
        print("   D = Payment Missing (paid in LMS)")
        print("   E = Legitimate (active collection)")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    export_unpaid_charters()
