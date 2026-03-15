#!/usr/bin/env python3
"""
Auto-update GL codes for vehicle maintenance and repair vendors.

This script updates tire shops, auto repair, and maintenance vendors to the correct
GL code 5100 - Vehicle Operating Expenses / Vehicle Maintenance & Repair.
"""

import sys
import os
import psycopg2
import argparse

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

# Correct GL code for vehicle maintenance and repair
MAINTENANCE_GL_CODE = "5100"
MAINTENANCE_GL_NAME = "Vehicle Operating Expenses"
MAINTENANCE_CATEGORY = "Vehicle Maintenance & Repair"

# Vehicle maintenance vendor patterns (LIKE patterns, lowercase)
MAINTENANCE_VENDOR_PATTERNS = [
    '%earls%tire%',
    '%earle%tire%',
    '%erles%auto%',
    '%eries%auto%',
    '%cal tire%',
    '%kal tire%',
    '%kal-tire%',
    '%kaltire%',
    '[kal tire]',
    '%kirks tire%',
    '%kirk%tire%',
    '%fountain tire%',
    '%ok tire%',
    '%big o tire%',
    '%canadian tire%',
    '%tire shop%',
    '%auto repair%',
    '%automotive%universe%',
    '%automotive%parts%',
    '%automotive%village%',
    '%automotive%uninverse%',
    '%muffler%',
    '%jiffy lube%',
    '%mr lube%',
    '%oil change%',
    '%quick lube%',
    '%brake%shop%',
    '%transmission%',
    '%bodyshop%',
    '%body shop%',
    '%collision%',
    '%parr%automotive%',
    '%jons%automotive%',
    '%mikasa%automotive%',
    '%mikassa%automotive%',
    '%peak%automotive%',
    '%park%automotive%',
]


def analyze_maintenance_vendors(cur):
    """Show current GL codes for maintenance vendors."""
    print("\n\n📊 CURRENT GL CODES FOR VEHICLE MAINTENANCE/REPAIR VENDORS:")
    print("-" * 140)
    print(f"{'Vendor':<45} {'GL Code':<12} {'GL Name':<45} {'Category':<25} {'Count':>6} {'Amount':>12}")
    print("-" * 140)
    
    # Build dynamic SQL with proper parameter placeholders
    vendor_like_clauses = []
    query_params = []
    for pattern in MAINTENANCE_VENDOR_PATTERNS:
        if pattern == '[kal tire]':
            vendor_like_clauses.append("vendor_name = '[KAL TIRE]'")
        else:
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


def find_misclassified_maintenance(cur):
    """Find maintenance receipts with incorrect GL codes."""
    print("\n\n🎯 RECEIPTS NEEDING GL CODE UPDATE:")
    print("-" * 140)
    
    # Build dynamic SQL with proper parameter placeholders
    vendor_like_clauses = []
    query_params = []
    for pattern in MAINTENANCE_VENDOR_PATTERNS:
        if pattern == '[kal tire]':
            vendor_like_clauses.append("vendor_name = '[KAL TIRE]'")
        else:
            vendor_like_clauses.append("LOWER(vendor_name) LIKE %s")
            query_params.append(pattern)
    
    vendor_conditions_sql = " OR ".join(vendor_like_clauses)
    query_params.append(MAINTENANCE_GL_CODE)  # For the != check
    
    cur.execute(f"""
        SELECT 
            COUNT(*) as total_count,
            SUM(gross_amount) as total_amount
        FROM receipts
        WHERE ({vendor_conditions_sql})
          AND (gl_account_code != %s OR gl_account_code IS NULL)
    """, query_params)
    
    total_count, total_amount = cur.fetchall()[0]
    
    print(f"\nFound {total_count} receipts with incorrect GL codes")
    print(f"Total Amount: ${total_amount:,.2f}\n")
    
    # Show breakdown by vendor
    query_params2 = []
    for pattern in MAINTENANCE_VENDOR_PATTERNS:
        if pattern != '[kal tire]':
            query_params2.append(pattern)
    
    query_params2.append(MAINTENANCE_GL_CODE)
    
    cur.execute(f"""
        SELECT 
            vendor_name,
            COUNT(*) as count,
            SUM(gross_amount) as total_amount,
            MIN(receipt_date) as first_date,
            MAX(receipt_date) as last_date
        FROM receipts
        WHERE ({vendor_conditions_sql})
          AND (gl_account_code != %s OR gl_account_code IS NULL)
        GROUP BY vendor_name
        ORDER BY count DESC
    """, query_params2)
    
    vendors = cur.fetchall()
    
    if vendors:
        print(f"{'Vendor':<45} {'Count':>6} {'Total Amount':>15} {'Date Range'}")
        print("-" * 100)
        
        for vendor, count, amount, first_date, last_date in vendors:
            print(f"{vendor[:44]:<45} {count:>6} ${amount:>13,.2f} {first_date} to {last_date}")
    
    return total_count


def update_maintenance_gl_codes(cur, conn):
    """Update all maintenance receipts to correct GL code."""
    print("\n\n" + "=" * 80)
    print("✏️ APPLYING UPDATES...")
    print("=" * 80 + "\n")
    
    # Build dynamic SQL with proper parameter placeholders
    vendor_like_clauses = []
    query_params = []
    for pattern in MAINTENANCE_VENDOR_PATTERNS:
        if pattern == '[kal tire]':
            vendor_like_clauses.append("vendor_name = '[KAL TIRE]'")
        else:
            vendor_like_clauses.append("LOWER(vendor_name) LIKE %s")
            query_params.append(pattern)
    
    vendor_conditions_sql = " OR ".join(vendor_like_clauses)
    
    # Build proper parameter order: SET values, then WHERE patterns, then != check
    update_params = [MAINTENANCE_GL_CODE, MAINTENANCE_GL_NAME, MAINTENANCE_CATEGORY]
    update_params.extend(query_params)  # Add vendor patterns
    update_params.append(MAINTENANCE_GL_CODE)  # Add != check
    
    cur.execute(f"""
        UPDATE receipts
        SET 
            gl_account_code = %s,
            gl_account_name = %s,
            category = %s,
            verified_by_edit = TRUE,
            verified_at = NOW(),
            verified_by_user = 'auto_maintenance_gl_update'
        WHERE ({vendor_conditions_sql})
          AND (gl_account_code != %s OR gl_account_code IS NULL)
    """, update_params)
    
    count = cur.rowcount
    conn.commit()
    
    print(f"✅ Updated {count} receipts successfully!")
    print(f"   GL Code: {MAINTENANCE_GL_CODE}")
    print(f"   GL Name: {MAINTENANCE_GL_NAME}")
    print(f"   Category: {MAINTENANCE_CATEGORY}")
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
    for pattern in MAINTENANCE_VENDOR_PATTERNS:
        if pattern == '[kal tire]':
            vendor_like_clauses.append("vendor_name = '[KAL TIRE]'")
        else:
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
        LIMIT 30
    """, query_params)
    
    for row in cur.fetchall():
        vendor, gl_code, gl_name, category, count, amount = row
        
        # Add checkmark if correct GL code
        prefix = "✅ " if gl_code == MAINTENANCE_GL_CODE else "   "
        
        gl_code_str = gl_code if gl_code else ""
        gl_name_str = gl_name if gl_name else ""
        category_str = category if category else ""
        
        print(f"{prefix}{vendor[:42]:<45} {gl_code_str:<12} {gl_name_str[:44]:<45} {category_str[:24]:<25} {count:>6} ${amount:>11,.2f}")


def main():
    parser = argparse.ArgumentParser(description='Auto-update vehicle maintenance GL codes')
    parser.add_argument('--write', action='store_true', help='Apply updates (default is dry-run)')
    
    args = parser.parse_args()
    
    print("🔍 VEHICLE MAINTENANCE & REPAIR GL CODE AUTO-UPDATE")
    print("=" * 80)
    print(f"Correct GL Code: {MAINTENANCE_GL_CODE} - {MAINTENANCE_GL_NAME}")
    print(f"Target Category: {MAINTENANCE_CATEGORY}")
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
        analyze_maintenance_vendors(cur)
        
        # Find misclassified receipts
        count = find_misclassified_maintenance(cur)
        
        # Apply updates if --write flag is set
        if args.write and count > 0:
            update_maintenance_gl_codes(cur, conn)
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
