#!/usr/bin/env python3
"""
Receipt Verification Audit Report
Shows which receipts have been manually verified during audit.
"""
import psycopg2
from datetime import datetime
import csv

DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***'
}

def generate_verification_report():
    print("📋 RECEIPT VERIFICATION AUDIT REPORT")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Overall summary
        print("\n🎯 OVERALL SUMMARY")
        print("-" * 80)
        cur.execute("SELECT * FROM receipt_verification_audit_summary")
        row = cur.fetchone()
        if row:
            total, verified, unverified, pct, first, last, users = row
            print(f"Total Business Receipts: {total:,}")
            print(f"Manually Verified: {verified:,} ({pct}%)")
            print(f"Unverified: {unverified:,}")
            if first:
                print(f"First Verification: {first}")
            if last:
                print(f"Last Verification: {last}")
            print(f"Unique Verifiers: {users or 0}")
        
        # Verification by user
        print("\n👤 VERIFICATION BY USER")
        print("-" * 80)
        cur.execute("""
            SELECT 
                COALESCE(verified_by_user, 'Unknown') as verifier,
                COUNT(*) as count,
                SUM(gross_amount) as total_amount,
                MIN(verified_at) as first_verified,
                MAX(verified_at) as last_verified
            FROM receipts
            WHERE verified_by_edit = TRUE
            GROUP BY verified_by_user
            ORDER BY count DESC
        """)
        rows = cur.fetchall()
        if rows:
            print(f"{'Verifier':<20} {'Count':>10} {'Total Amount':>15} {'First':>20} {'Last':>20}")
            print("-" * 90)
            for verifier, count, amount, first, last in rows:
                amount_str = f"${amount:,.2f}" if amount else "$0.00"
                first_str = first.strftime('%Y-%m-%d %H:%M') if first else ''
                last_str = last.strftime('%Y-%m-%d %H:%M') if last else ''
                print(f"{verifier:<20} {count:>10,} {amount_str:>15} {first_str:>20} {last_str:>20}")
        else:
            print("(No verified receipts yet)")
        
        # Verification by date
        print("\n📅 VERIFICATION BY DATE")
        print("-" * 80)
        cur.execute("""
            SELECT 
                DATE(verified_at) as verify_date,
                COUNT(*) as count,
                SUM(gross_amount) as total_amount
            FROM receipts
            WHERE verified_by_edit = TRUE
            GROUP BY DATE(verified_at)
            ORDER BY verify_date DESC
            LIMIT 30
        """)
        rows = cur.fetchall()
        if rows:
            print(f"{'Date':<15} {'Count':>10} {'Total Amount':>15}")
            print("-" * 45)
            for verify_date, count, amount in rows:
                amount_str = f"${amount:,.2f}" if amount else "$0.00"
                print(f"{verify_date:<15} {count:>10,} {amount_str:>15}")
        else:
            print("(No verified receipts yet)")
        
        # Unverified receipts by category
        print("\n⚠️  UNVERIFIED RECEIPTS BY CATEGORY")
        print("-" * 80)
        cur.execute("""
            SELECT 
                COALESCE(category, 'Uncategorized') as cat,
                COUNT(*) as count,
                SUM(gross_amount) as total_amount
            FROM receipts
            WHERE (verified_by_edit = FALSE OR verified_by_edit IS NULL)
              AND (business_personal != 'personal' OR business_personal IS NULL)
            GROUP BY category
            ORDER BY count DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        if rows:
            print(f"{'Category':<30} {'Count':>10} {'Total Amount':>15}")
            print("-" * 60)
            for cat, count, amount in rows:
                amount_str = f"${amount:,.2f}" if amount else "$0.00"
                print(f"{cat:<30} {count:>10,} {amount_str:>15}")
        
        # Recent verified receipts
        print("\n🔍 RECENTLY VERIFIED RECEIPTS (Last 20)")
        print("-" * 80)
        cur.execute("""
            SELECT 
                receipt_id,
                receipt_date,
                vendor_name,
                gross_amount,
                category,
                verified_at,
                verified_by_user
            FROM receipts
            WHERE verified_by_edit = TRUE
            ORDER BY verified_at DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        if rows:
            print(f"{'ID':<8} {'Date':<12} {'Vendor':<25} {'Amount':>12} {'Category':<15} {'Verified At':<20}")
            print("-" * 100)
            for rid, rdate, vendor, amount, cat, verified_at, user in rows:
                vendor_str = (vendor or '')[:23]
                cat_str = (cat or '')[:13]
                amount_str = f"${amount:,.2f}" if amount else "$0.00"
                verified_str = verified_at.strftime('%Y-%m-%d %H:%M') if verified_at else ''
                print(f"{rid:<8} {rdate} {vendor_str:<25} {amount_str:>12} {cat_str:<15} {verified_str:<20}")
        else:
            print("(No verified receipts yet)")
        
        # Export to CSV
        print("\n💾 Exporting detailed report to CSV...")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_file = f"l:/limo/reports/receipt_verification_audit_{timestamp}.csv"
        
        cur.execute("""
            SELECT 
                receipt_id,
                receipt_date,
                vendor_name,
                gross_amount,
                category,
                gl_account_code,
                verified_by_edit,
                verified_at,
                verified_by_user,
                CASE 
                    WHEN verified_by_edit THEN 'Manually Verified'
                    WHEN banking_transaction_id IS NOT NULL THEN 'Banking Linked'
                    ELSE 'Unverified'
                END as verification_status
            FROM receipts
            WHERE business_personal != 'personal' OR business_personal IS NULL
            ORDER BY verified_at DESC NULLS LAST, receipt_date DESC
        """)
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Receipt ID', 'Date', 'Vendor', 'Amount', 'Category', 'GL Account',
                'Verified By Edit', 'Verified At', 'Verified By User', 'Verification Status'
            ])
            for row in cur.fetchall():
                writer.writerow(row)
        
        print(f"   ✅ Exported to: {csv_file}")
        
        print("\n" + "=" * 80)
        print("✅ Report Complete")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error generating report: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    generate_verification_report()
