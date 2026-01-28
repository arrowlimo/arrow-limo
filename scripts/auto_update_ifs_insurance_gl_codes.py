#!/usr/bin/env python3
"""
Auto-update GL codes for IFS Financial (commercial auto insurance).

This script identifies IFS Financial receipts and updates them to the correct
commercial auto insurance GL code.
"""

import sys
import os
import psycopg2
from datetime import datetime
import argparse

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

# Correct GL code for commercial auto insurance
INSURANCE_GL_CODE = "5330"
INSURANCE_GL_NAME = "Insurance - Auto"
INSURANCE_CATEGORY = "Insurance - Auto"

# IFS Financial vendor patterns (LIKE patterns, lowercase)
IFS_VENDOR_PATTERNS = [
    '%ifs financial%',
    '%ifs finance%',
]


def analyze_ifs_vendors(cur):
    """Show current GL codes for IFS Financial vendors."""
    print("\n\n📊 CURRENT GL CODES FOR IFS FINANCIAL:")
    print("-" * 140)
    print(f"{'Vendor':<45} {'GL Code':<12} {'GL Name':<45} {'Category':<25} {'Count':>6} {'Amount':>12}")
    print("-" * 140)
    
    # Build dynamic SQL with proper parameter placeholders
    vendor_like_clauses = []
    query_params = []
    for pattern in IFS_VENDOR_PATTERNS:
        vendor_like_clauses.append("LOWER(vendor_name) LIKE %s")
        query_params.append(pattern)
    
    vendor_conditions_sql = " OR ".join(vendor_like_clauses)
    
    cur.execute(f"""
        SELECT 
            vendor_name,
            gl_account_code,
            gl_account_name,
            category,
            COUNT(*) as count,
            SUM(gross_amount) as total_amount
        FROM receipts
        WHERE ({vendor_conditions_sql})
        GROUP BY vendor_name, gl_account_code, gl_account_name, category
        ORDER BY count DESC
    """, query_params)
    
    total_count = 0
    total_amount = 0
    
    for row in cur.fetchall():
        vendor, gl_code, gl_name, category, count, amount = row
        total_count += count
        total_amount += amount or 0
        
        gl_code_str = gl_code if gl_code else ""
        gl_name_str = gl_name if gl_name else ""
        category_str = category if category else ""
        
        print(f"{vendor[:44]:<45} {gl_code_str:<12} {gl_name_str[:44]:<45} {category_str[:24]:<25} {count:>6} ${amount:>11,.2f}")
    
    print()
    print(f"Total: {total_count} receipts, ${total_amount:,.2f}")


def find_misclassified_ifs(cur):
    """Find IFS Financial receipts with incorrect GL codes."""
    print("\n\n🎯 RECEIPTS NEEDING GL CODE UPDATE:")
    print("-" * 140)
    
    # Build dynamic SQL with proper parameter placeholders
    vendor_like_clauses = []
    query_params = []
    for pattern in IFS_VENDOR_PATTERNS:
        vendor_like_clauses.append("LOWER(vendor_name) LIKE %s")
        query_params.append(pattern)
    
    vendor_conditions_sql = " OR ".join(vendor_like_clauses)
    query_params.append(INSURANCE_GL_CODE)  # For the != check
    
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
    
    results = cur.fetchall()
    
    print(f"\nFound {len(results)} receipts with incorrect GL codes:\n")
    
    if results:
        print(f"{'ID':<8} {'Date':<12} {'Vendor':<40} {'Amount':>12} {'Current GL':<12} {'Current Category':<25}")
        print("-" * 140)
        
        total_amount = 0
        
        for row in results[:50]:  # Show first 50
            receipt_id, date, vendor, amount, gl_code, gl_name, category = row
            total_amount += amount or 0
            
            gl_str = gl_code if gl_code else "NULL"
            cat_str = category if category else ""
            
            print(f"{receipt_id:<8} {date} {vendor[:39]:<40} ${amount:>10,.2f} {gl_str:<12} {cat_str[:24]:<25}")
        
        if len(results) > 50:
            print(f"\n... and {len(results) - 50} more")
        
        print(f"\n💰 Total Amount: ${total_amount:,.2f}")
    
    return results


def update_ifs_gl_codes(cur, conn):
    """Update all IFS Financial receipts to correct GL code."""
    print("\n\n" + "=" * 80)
    print("✏️ APPLYING UPDATES...")
    print("=" * 80 + "\n")
    
    # Build dynamic SQL with proper parameter placeholders
    vendor_like_clauses = []
    query_params = []
    for pattern in IFS_VENDOR_PATTERNS:
        vendor_like_clauses.append("LOWER(vendor_name) LIKE %s")
        query_params.append(pattern)
    
    vendor_conditions_sql = " OR ".join(vendor_like_clauses)
    
    # Build proper parameter order: SET values, then WHERE patterns, then != check
    update_params = [INSURANCE_GL_CODE, INSURANCE_GL_NAME, INSURANCE_CATEGORY]
    update_params.extend(query_params)  # Add vendor patterns
    update_params.append(INSURANCE_GL_CODE)  # Add != check
    
    cur.execute(f"""
        UPDATE receipts
        SET 
            gl_account_code = %s,
            gl_account_name = %s,
            category = %s,
            verified_by_edit = TRUE,
            verified_at = NOW(),
            verified_by_user = 'auto_ifs_insurance_update'
        WHERE ({vendor_conditions_sql})
          AND (gl_account_code != %s OR gl_account_code IS NULL)
    """, update_params)
    
    count = cur.rowcount
    conn.commit()
    
    print(f"✅ Updated {count} receipts successfully!")
    print(f"   GL Code: {INSURANCE_GL_CODE}")
    print(f"   GL Name: {INSURANCE_GL_NAME}")
    print(f"   Category: {INSURANCE_CATEGORY}")
    print(f"   Also marked as verified\n")
    
    return count


def show_updated_status(cur):
    """Show final status after updates."""
    print("\n📊 UPDATED STATUS:")
    print("-" * 140)
    print(f"{'Vendor':<45} {'GL Code':<12} {'GL Name':<45} {'Category':<25} {'Count':>6} {'Amount':>12}")
    print("-" * 140)
    
    # Build dynamic SQL with proper parameter placeholders
    vendor_like_clauses = []
    query_params = []
    for pattern in IFS_VENDOR_PATTERNS:
        vendor_like_clauses.append("LOWER(vendor_name) LIKE %s")
        query_params.append(pattern)
    
    vendor_conditions_sql = " OR ".join(vendor_like_clauses)
    
    cur.execute(f"""
        SELECT 
            vendor_name,
            gl_account_code,
            gl_account_name,
            category,
            COUNT(*) as count,
            SUM(gross_amount) as total_amount
        FROM receipts
        WHERE ({vendor_conditions_sql})
        GROUP BY vendor_name, gl_account_code, gl_account_name, category
        ORDER BY count DESC
    """, query_params)
    
    for row in cur.fetchall():
        vendor, gl_code, gl_name, category, count, amount = row
        
        # Add checkmark if correct GL code
        prefix = "✅ " if gl_code == INSURANCE_GL_CODE else "   "
        
        gl_code_str = gl_code if gl_code else ""
        gl_name_str = gl_name if gl_name else ""
        category_str = category if category else ""
        
        print(f"{prefix}{vendor[:42]:<45} {gl_code_str:<12} {gl_name_str[:44]:<45} {category_str[:24]:<25} {count:>6} ${amount:>11,.2f}")


def main():
    parser = argparse.ArgumentParser(description='Auto-update IFS Financial insurance GL codes')
    parser.add_argument('--write', action='store_true', help='Apply updates (default is dry-run)')
    parser.add_argument('--add-vendor', type=str, help='Add a vendor pattern to search for')
    
    args = parser.parse_args()
    
    if args.add_vendor:
        IFS_VENDOR_PATTERNS.append(f'%{args.add_vendor.lower()}%')
        print(f"Added vendor pattern: %{args.add_vendor.lower()}%\n")
    
    print("🔍 IFS FINANCIAL INSURANCE GL CODE AUTO-UPDATE")
    print("=" * 80)
    print(f"Correct GL Code: {INSURANCE_GL_CODE} - {INSURANCE_GL_NAME}")
    print(f"Target Category: {INSURANCE_CATEGORY}")
    print("=" * 80)
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()
        
        # Show current status
        analyze_ifs_vendors(cur)
        
        # Find misclassified receipts
        results = find_misclassified_ifs(cur)
        
        # Apply updates if --write flag is set
        if args.write and results:
            update_ifs_gl_codes(cur, conn)
            show_updated_status(cur)
        else:
            print("\n" + "=" * 80)
            print("🔒 DRY RUN - No changes made")
            print("=" * 80)
            print("\nTo apply these updates, run with --write flag")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
