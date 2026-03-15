#!/usr/bin/env python3
"""
Auto-update GL codes for Client Beverage purchases
Finds liquor/beverage vendors with wrong GL codes and fixes them
"""
import psycopg2
import argparse
from datetime import datetime

DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***'
}

# Correct GL code for client beverages
CLIENT_BEVERAGE_GL_CODE = '4115'
CLIENT_BEVERAGE_GL_NAME = 'Client Beverage Service Charges'
CLIENT_BEVERAGE_CATEGORY = 'Client Beverages'

# Vendor patterns that should be client beverages
BEVERAGE_VENDOR_PATTERNS = [
    '%liquor barn%',
    '%curvy bottle%',
    '%liquor depot%',
    '%wine%spirit%',
    '%beer%wine%',
    '%bottle shop%',
    '%liquor store%',
    '%wine shop%',
    '%spirits%',
    '%co-op%liquor%',
    '%sobeys%liquor%',
    '%safeway%liquor%',
]

def find_misclassified_beverages(dry_run=True):
    """Find and optionally fix client beverage receipts with wrong GL codes."""
    
    print("🔍 CLIENT BEVERAGE GL CODE AUTO-UPDATE")
    print("=" * 80)
    print(f"Correct GL Code: {CLIENT_BEVERAGE_GL_CODE} - {CLIENT_BEVERAGE_GL_NAME}")
    print(f"Target Category: {CLIENT_BEVERAGE_CATEGORY}")
    print("=" * 80)
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # First, show current status of these vendors
        print("\n📊 CURRENT GL CODES FOR BEVERAGE VENDORS:")
        print("-" * 120)
        
        vendor_conditions = " OR ".join([f"LOWER(vendor_name) LIKE '{pattern}'" for pattern in BEVERAGE_VENDOR_PATTERNS])
        
        cur.execute(f"""
            SELECT 
                vendor_name,
                gl_account_code,
                gl_account_name,
                category,
                COUNT(*) as count,
                SUM(gross_amount) as total_amount
            FROM receipts
            WHERE {vendor_conditions}
            GROUP BY vendor_name, gl_account_code, gl_account_name, category
            ORDER BY vendor_name, count DESC
        """)
        
        current_status = cur.fetchall()
        
        if current_status:
            print(f"{'Vendor':<35} {'GL Code':<15} {'GL Name':<30} {'Category':<20} {'Count':>8} {'Amount':>15}")
            print("-" * 120)
            for vendor, gl_code, gl_name, category, count, amount in current_status:
                vendor_str = (vendor or '')[:33]
                gl_code_str = (gl_code or '')[:13]
                gl_name_str = (gl_name or '')[:28]
                category_str = (category or '')[:18]
                amount_str = f"${amount:,.2f}" if amount else "$0.00"
                print(f"{vendor_str:<35} {gl_code_str:<15} {gl_name_str:<30} {category_str:<20} {count:>8,} {amount_str:>15}")
        else:
            print("(No beverage vendors found)")
        
        # Find receipts that need updating
        print("\n\n🎯 RECEIPTS NEEDING GL CODE UPDATE:")
        print("-" * 120)
        
        # Build dynamic SQL with proper parameter placeholders
        vendor_like_clauses = []
        query_params = []
        for pattern in BEVERAGE_VENDOR_PATTERNS:
            vendor_like_clauses.append("LOWER(vendor_name) LIKE %s")
            query_params.append(pattern)
        
        vendor_conditions_sql = " OR ".join(vendor_like_clauses)
        query_params.append(CLIENT_BEVERAGE_GL_CODE)  # For the != check
        
        cur.execute(f"""
            SELECT 
                receipt_id,
                receipt_date,
                vendor_name,
                gross_amount,
                gl_account_code,
                gl_account_name,
                category
            FROM receipts
            WHERE ({vendor_conditions_sql})
              AND (gl_account_code != %s OR gl_account_code IS NULL)
            ORDER BY receipt_date DESC, vendor_name
        """, query_params)
        
        to_update = cur.fetchall()
        
        if not to_update:
            print("✅ All beverage receipts already have correct GL code!")
            return
        
        print(f"\nFound {len(to_update)} receipts with incorrect GL codes:")
        print(f"\n{'ID':<8} {'Date':<12} {'Vendor':<35} {'Amount':>12} {'Current GL':<15} {'Current Category':<20}")
        print("-" * 120)
        
        total_amount = 0
        for receipt_id, rdate, vendor, amount, gl_code, gl_name, category in to_update[:50]:
            vendor_str = (vendor or '')[:33]
            gl_code_str = (gl_code or 'NULL')[:13]
            category_str = (category or 'NULL')[:18]
            amount_str = f"${amount:,.2f}" if amount else "$0.00"
            print(f"{receipt_id:<8} {rdate} {vendor_str:<35} {amount_str:>12} {gl_code_str:<15} {category_str:<20}")
            total_amount += amount or 0
        
        if len(to_update) > 50:
            print(f"... and {len(to_update) - 50} more")
        
        print(f"\n💰 Total Amount: ${total_amount:,.2f}")
        
        # Breakdown by vendor
        print("\n\n📈 BREAKDOWN BY VENDOR:")
        print("-" * 80)
        
        # Build dynamic SQL with proper parameter placeholders  
        vendor_like_clauses2 = []
        query_params2 = []
        for pattern in BEVERAGE_VENDOR_PATTERNS:
            vendor_like_clauses2.append("LOWER(vendor_name) LIKE %s")
            query_params2.append(pattern)
        
        vendor_conditions_sql2 = " OR ".join(vendor_like_clauses2)
        query_params2.append(CLIENT_BEVERAGE_GL_CODE)  # For the != check
        
        cur.execute(f"""
            SELECT 
                vendor_name,
                COUNT(*) as count,
                SUM(gross_amount) as total_amount,
                MIN(receipt_date) as first_date,
                MAX(receipt_date) as last_date
            FROM receipts
            WHERE ({vendor_conditions_sql2})
              AND (gl_account_code != %s OR gl_account_code IS NULL)
            GROUP BY vendor_name
            ORDER BY count DESC
        """, query_params2)
        
        vendor_breakdown = cur.fetchall()
        
        print(f"{'Vendor':<35} {'Count':>8} {'Total Amount':>15} {'Date Range':<25}")
        print("-" * 80)
        for vendor, count, amount, first_date, last_date in vendor_breakdown:
            vendor_str = (vendor or '')[:33]
            amount_str = f"${amount:,.2f}" if amount else "$0.00"
            date_range = f"{first_date} to {last_date}"
            print(f"{vendor_str:<35} {count:>8,} {amount_str:>15} {date_range:<25}")
        
        if dry_run:
            print("\n" + "=" * 80)
            print("🔒 DRY RUN - No changes made")
            print("=" * 80)
            print("\nTo apply these updates, run with --write flag")
            return
        
        # Apply updates
        print("\n" + "=" * 80)
        print("✏️ APPLYING UPDATES...")
        print("=" * 80)
        
        receipt_ids = [row[0] for row in to_update]
        
        cur.execute(f"""
            UPDATE receipts
            SET gl_account_code = %s,
                gl_account_name = %s,
                category = %s,
                verified_by_edit = TRUE,
                verified_at = NOW(),
                verified_by_user = 'auto_gl_update'
            WHERE receipt_id = ANY(%s)
        """, (CLIENT_BEVERAGE_GL_CODE, CLIENT_BEVERAGE_GL_NAME, CLIENT_BEVERAGE_CATEGORY, receipt_ids))
        
        updated_count = cur.rowcount
        conn.commit()
        
        print(f"\n✅ Updated {updated_count} receipts successfully!")
        print(f"   GL Code: {CLIENT_BEVERAGE_GL_CODE}")
        print(f"   GL Name: {CLIENT_BEVERAGE_GL_NAME}")
        print(f"   Category: {CLIENT_BEVERAGE_CATEGORY}")
        print(f"   Also marked as verified")
        
        # Show summary after update
        print("\n\n📊 UPDATED STATUS:")
        print("-" * 120)
        
        cur.execute(f"""
            SELECT 
                vendor_name,
                gl_account_code,
                gl_account_name,
                category,
                COUNT(*) as count,
                SUM(gross_amount) as total_amount
            FROM receipts
            WHERE {vendor_conditions}
            GROUP BY vendor_name, gl_account_code, gl_account_name, category
            ORDER BY vendor_name, count DESC
        """)
        
        updated_status = cur.fetchall()
        
        print(f"{'Vendor':<35} {'GL Code':<15} {'GL Name':<30} {'Category':<20} {'Count':>8} {'Amount':>15}")
        print("-" * 120)
        for vendor, gl_code, gl_name, category, count, amount in updated_status:
            vendor_str = (vendor or '')[:33]
            gl_code_str = (gl_code or '')[:13]
            gl_name_str = (gl_name or '')[:28]
            category_str = (category or '')[:18]
            amount_str = f"${amount:,.2f}" if amount else "$0.00"
            status = "✅" if gl_code == CLIENT_BEVERAGE_GL_CODE else "⚠️"
            print(f"{status} {vendor_str:<33} {gl_code_str:<15} {gl_name_str:<30} {category_str:<20} {count:>8,} {amount_str:>15}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def main():
    parser = argparse.ArgumentParser(description='Auto-update GL codes for client beverage purchases')
    parser.add_argument('--write', action='store_true', help='Apply updates (default is dry-run)')
    parser.add_argument('--add-vendor', action='append', help='Add additional vendor pattern (e.g., "%%wine%%store%%")')
    
    args = parser.parse_args()
    
    # Add custom vendor patterns if provided
    if args.add_vendor:
        BEVERAGE_VENDOR_PATTERNS.extend(args.add_vendor)
        print(f"\n📝 Added custom vendor patterns: {args.add_vendor}\n")
    
    find_misclassified_beverages(dry_run=not args.write)

if __name__ == '__main__':
    main()
