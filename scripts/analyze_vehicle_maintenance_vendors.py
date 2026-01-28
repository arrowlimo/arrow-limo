#!/usr/bin/env python3
"""
Analyze vehicle maintenance and repair vendors to identify those needing GL code updates.

This script searches for tire shops, auto repair, and maintenance vendors and shows
which ones have incorrect GL codes that should be updated to vehicle maintenance.
"""

import sys
import os
import psycopg2

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

# Correct GL code for vehicle maintenance and repair
MAINTENANCE_GL_CODE = "5100"
MAINTENANCE_GL_NAME = "Vehicle Operating Expenses"
MAINTENANCE_CATEGORY = "Vehicle Maintenance & Repair"

# Vehicle maintenance vendor patterns (LIKE patterns, lowercase)
MAINTENANCE_VENDOR_PATTERNS = [
    '%earls%tire%',
    '%earle%tire%',
    '%cal tire%',
    '%kal tire%',
    '%kirks tire%',
    '%kirk%tire%',
    '%fountain tire%',
    '%ok tire%',
    '%big o tire%',
    '%canadian tire%',  # Non-gas Canadian Tire
    '%kaltire%',
    '%tire shop%',
    '%auto repair%',
    '%automotive%',
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
    '%kal-tire%',
]


def analyze_maintenance_vendors(cur):
    """Show all potential maintenance vendors and their GL codes."""
    print("\n\n📊 POTENTIAL VEHICLE MAINTENANCE/REPAIR VENDORS:")
    print("=" * 150)
    print(f"{'Vendor':<50} {'GL Code':<10} {'GL Name':<40} {'Category':<25} {'Count':>6} {'Amount':>12}")
    print("=" * 150)
    
    # Build dynamic SQL with proper parameter placeholders
    vendor_like_clauses = []
    query_params = []
    for pattern in MAINTENANCE_VENDOR_PATTERNS:
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
        ORDER BY vendor_name, count DESC
    """, query_params)
    
    results = cur.fetchall()
    
    if not results:
        print("\n❌ No maintenance vendors found matching patterns")
        return []
    
    current_vendor = None
    for row in results:
        vendor, gl_code, gl_name, category, count, amount = row
        
        # Add separator between different vendors
        if current_vendor != vendor:
            if current_vendor is not None:
                print("-" * 150)
            current_vendor = vendor
        
        gl_code_str = gl_code if gl_code else "NULL"
        gl_name_str = gl_name if gl_name else ""
        category_str = category if category else ""
        
        # Flag if not the correct GL code
        flag = "⚠️ " if gl_code != MAINTENANCE_GL_CODE else "✅ "
        
        print(f"{flag}{vendor[:48]:<50} {gl_code_str:<10} {gl_name_str[:39]:<40} {category_str[:24]:<25} {count:>6} ${amount:>11,.2f}")
    
    return results


def find_incorrect_gl_codes(cur):
    """Find maintenance vendors with incorrect GL codes - grouped by vendor."""
    print("\n\n🔍 VENDORS NEEDING GL CODE REVIEW:")
    print("=" * 150)
    
    # Build dynamic SQL with proper parameter placeholders
    vendor_like_clauses = []
    query_params = []
    for pattern in MAINTENANCE_VENDOR_PATTERNS:
        vendor_like_clauses.append("LOWER(vendor_name) LIKE %s")
        query_params.append(pattern)
    
    vendor_conditions_sql = " OR ".join(vendor_like_clauses)
    query_params.append(MAINTENANCE_GL_CODE)  # For the != check
    
    cur.execute(f"""
        SELECT 
            vendor_name,
            gl_account_code,
            gl_account_name,
            category,
            COUNT(*) as count,
            SUM(gross_amount) as total_amount,
            MIN(receipt_date) as first_date,
            MAX(receipt_date) as last_date
        FROM receipts
        WHERE ({vendor_conditions_sql})
          AND (gl_account_code != %s OR gl_account_code IS NULL)
        GROUP BY vendor_name, gl_account_code, gl_account_name, category
        ORDER BY vendor_name, count DESC
    """, query_params)
    
    results = cur.fetchall()
    
    if not results:
        print("\n✅ All maintenance vendors already have correct GL codes!")
        return []
    
    print(f"\n{'Vendor':<50} {'Current GL':<10} {'Category':<25} {'Count':>6} {'Amount':>12} {'Date Range'}")
    print("-" * 150)
    
    total_receipts = 0
    total_amount = 0
    vendors_dict = {}
    
    for row in results:
        vendor, gl_code, gl_name, category, count, amount, first_date, last_date = row
        total_receipts += count
        total_amount += amount or 0
        
        gl_code_str = gl_code if gl_code else "NULL"
        category_str = category if category else ""
        
        print(f"{vendor[:49]:<50} {gl_code_str:<10} {category_str[:24]:<25} {count:>6} ${amount:>11,.2f} {first_date} to {last_date}")
        
        # Track unique vendors
        if vendor not in vendors_dict:
            vendors_dict[vendor] = {'count': 0, 'amount': 0}
        vendors_dict[vendor]['count'] += count
        vendors_dict[vendor]['amount'] += amount or 0
    
    print("\n" + "=" * 150)
    print(f"TOTAL: {len(vendors_dict)} unique vendors, {total_receipts} receipts, ${total_amount:,.2f}")
    
    return results


def show_suspicious_categories(cur):
    """Show receipts that might be fuel but are categorized as maintenance."""
    print("\n\n⚠️  SUSPICIOUS: Checking for potential fuel mis-categorized as maintenance:")
    print("=" * 150)
    
    # Check Canadian Tire (could be fuel or maintenance)
    cur.execute("""
        SELECT 
            vendor_name,
            description,
            gross_amount,
            gl_account_code,
            category,
            receipt_date,
            receipt_id
        FROM receipts
        WHERE LOWER(vendor_name) LIKE '%canadian tire%'
          AND (LOWER(description) LIKE '%gas%' 
               OR LOWER(description) LIKE '%fuel%'
               OR LOWER(description) LIKE '%petroleum%')
        ORDER BY receipt_date DESC
        LIMIT 20
    """)
    
    gas_results = cur.fetchall()
    
    if gas_results:
        print(f"\n🚨 Found {len(gas_results)} Canadian Tire receipts with fuel-related descriptions:")
        print(f"{'ID':<8} {'Date':<12} {'Vendor':<30} {'Description':<30} {'Amount':>10} {'GL Code':<10}")
        print("-" * 120)
        for row in gas_results:
            vendor, desc, amount, gl_code, category, date, receipt_id = row
            desc_str = (desc or "")[:29]
            print(f"{receipt_id:<8} {date} {vendor[:29]:<30} {desc_str:<30} ${amount:>8,.2f} {gl_code or 'NULL':<10}")
    else:
        print("\n✅ No suspicious fuel receipts found in maintenance vendors")


def show_sample_receipts_by_vendor(cur):
    """Show sample receipts for each vendor to help identify correct categorization."""
    print("\n\n📋 SAMPLE RECEIPTS BY VENDOR (for categorization verification):")
    print("=" * 150)
    
    # Build dynamic SQL with proper parameter placeholders
    vendor_like_clauses = []
    query_params = []
    for pattern in MAINTENANCE_VENDOR_PATTERNS:
        vendor_like_clauses.append("LOWER(vendor_name) LIKE %s")
        query_params.append(pattern)
    
    vendor_conditions_sql = " OR ".join(vendor_like_clauses)
    query_params.append(MAINTENANCE_GL_CODE)  # For the != check
    
    cur.execute(f"""
        WITH ranked_receipts AS (
            SELECT 
                vendor_name,
                receipt_id,
                receipt_date,
                description,
                gross_amount,
                gl_account_code,
                category,
                ROW_NUMBER() OVER (PARTITION BY vendor_name ORDER BY receipt_date DESC) as rn
            FROM receipts
            WHERE ({vendor_conditions_sql})
              AND (gl_account_code != %s OR gl_account_code IS NULL)
        )
        SELECT 
            vendor_name,
            receipt_id,
            receipt_date,
            description,
            gross_amount,
            gl_account_code,
            category
        FROM ranked_receipts
        WHERE rn <= 3
        ORDER BY vendor_name, receipt_date DESC
    """, query_params)
    
    results = cur.fetchall()
    
    if results:
        current_vendor = None
        for row in results:
            vendor, receipt_id, date, desc, amount, gl_code, category = row
            
            if current_vendor != vendor:
                if current_vendor is not None:
                    print("-" * 150)
                current_vendor = vendor
                print(f"\n{vendor}:")
            
            desc_str = (desc or "")[:50]
            gl_str = gl_code if gl_code else "NULL"
            cat_str = category if category else ""
            print(f"  {receipt_id:<8} {date} ${amount:>8,.2f} GL:{gl_str:<10} {cat_str[:20]:<20} | {desc_str}")


def main():
    print("🔍 VEHICLE MAINTENANCE & REPAIR VENDOR ANALYSIS")
    print("=" * 80)
    print(f"Target GL Code: {MAINTENANCE_GL_CODE} - {MAINTENANCE_GL_NAME}")
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
        
        # Show all maintenance vendors
        analyze_maintenance_vendors(cur)
        
        # Show vendors needing updates
        find_incorrect_gl_codes(cur)
        
        # Check for suspicious categorizations
        show_suspicious_categories(cur)
        
        # Show sample receipts
        show_sample_receipts_by_vendor(cur)
        
        print("\n\n" + "=" * 80)
        print("📝 NEXT STEPS:")
        print("=" * 80)
        print("Review the vendors listed above and confirm which should be updated.")
        print("If approved, create a specific update script for these vendors.")
        print("\nNote: Canadian Tire receipts may need manual review to separate:")
        print("  - Fuel purchases (GL 5306)")
        print("  - Auto parts/maintenance (GL 5100)")
        print("  - Other supplies (keep existing GL codes)")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
