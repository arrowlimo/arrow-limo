#!/usr/bin/env python3
"""
Auto-update GL codes for fuel purchases and verify vehicle assignment on split receipts.

This script:
1. Identifies fuel vendor receipts with incorrect GL codes
2. Updates them to the correct fuel GL code (5306 - Fuel)
3. Verifies split receipts with fuel have vehicle_id and vehicle_plate
4. Reports any fuel receipts missing vehicle information
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
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

# Correct GL code for fuel
FUEL_GL_CODE = "5306"
FUEL_GL_NAME = "Fuel"
FUEL_CATEGORY = "Fuel"

# Fuel vendor patterns (LIKE patterns, lowercase)
FUEL_VENDOR_PATTERNS = [
    '%fas gas%',
    '%petro canada%',
    '%petro-canada%',
    '%shell%',
    '%esso%',
    '%husky%',
    '%chevron%',
    '%co-op gas%',
    '%coop gas%',
    '%costco gas%',
    '%safeway fuel%',
    '%superstore fuel%',
    '%7-eleven%',
    '%circle k%',
    '%gas plus%',
    '%centex%',
    '%pioneer gas%',
    '%canadian tire gas%',
    '%cdn tire gas%',
    '%ultramar%',
    '%mohawk%',
]


def analyze_fuel_vendors(cur):
    """Show current GL codes for fuel vendors."""
    print("\n\n📊 CURRENT GL CODES FOR FUEL VENDORS:")
    print("-" * 140)
    print(f"{'Vendor':<45} {'GL Code':<12} {'GL Name':<45} {'Category':<25} {'Count':>6} {'Amount':>12}")
    print("-" * 140)
    
    # Build dynamic SQL with proper parameter placeholders
    vendor_like_clauses = []
    query_params = []
    for pattern in FUEL_VENDOR_PATTERNS:
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


def find_misclassified_fuel(cur):
    """Find fuel receipts with incorrect GL codes."""
    print("\n\n🎯 RECEIPTS NEEDING GL CODE UPDATE:")
    print("-" * 140)
    
    # Build dynamic SQL with proper parameter placeholders
    vendor_like_clauses = []
    query_params = []
    for pattern in FUEL_VENDOR_PATTERNS:
        vendor_like_clauses.append("LOWER(vendor_name) LIKE %s")
        query_params.append(pattern)
    
    vendor_conditions_sql = " OR ".join(vendor_like_clauses)
    query_params.append(FUEL_GL_CODE)  # For the != check
    
    cur.execute(f"""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            gl_account_code,
            gl_account_name,
            category,
            vehicle_id,
            split_group_id
        FROM receipts
        WHERE ({vendor_conditions_sql})
          AND (gl_account_code != %s OR gl_account_code IS NULL)
        ORDER BY receipt_date DESC, vendor_name
    """, query_params)
    
    results = cur.fetchall()
    
    print(f"\nFound {len(results)} receipts with incorrect GL codes:\n")
    
    if results:
        print(f"{'ID':<8} {'Date':<12} {'Vendor':<40} {'Amount':>12} {'Current GL':<12} {'Current Category':<25} {'Vehicle':<10} {'Split':<8}")
        print("-" * 140)
        
        total_amount = 0
        missing_vehicle_count = 0
        
        for row in results[:50]:  # Show first 50
            receipt_id, date, vendor, amount, gl_code, gl_name, category, vehicle_id, split_id = row
            total_amount += amount or 0
            
            gl_str = gl_code if gl_code else "NULL"
            cat_str = category if category else ""
            vehicle_str = str(vehicle_id) if vehicle_id else ""
            split_str = str(split_id) if split_id else ""
            
            # Flag if missing vehicle info
            if not vehicle_id:
                missing_vehicle_count += 1
                vehicle_str = "⚠️ " + vehicle_str if vehicle_str else "⚠️"
            
            print(f"{receipt_id:<8} {date} {vendor[:39]:<40} ${amount:>10,.2f} {gl_str:<12} {cat_str[:24]:<25} {vehicle_str:<10} {split_str:<8}")
        
        if len(results) > 50:
            print(f"\n... and {len(results) - 50} more")
        
        print(f"\n💰 Total Amount: ${total_amount:,.2f}")
        
        if missing_vehicle_count > 0:
            print(f"⚠️  {missing_vehicle_count} receipts missing vehicle assignment")
    
    return results


def check_split_fuel_vehicle_assignment(cur):
    """Check split receipts with fuel to ensure vehicle assignment."""
    print("\n\n🔍 SPLIT RECEIPTS WITH FUEL GL CODE:")
    print("-" * 140)
    
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.gross_amount,
            r.gl_account_code,
            r.vehicle_id,
            r.split_group_id,
            COUNT(*) OVER (PARTITION BY r.split_group_id) as split_count
        FROM receipts r
        WHERE r.split_group_id IS NOT NULL
          AND r.gl_account_code = %s
        ORDER BY r.split_group_id, r.receipt_date DESC
    """, (FUEL_GL_CODE,))
    
    results = cur.fetchall()
    
    if not results:
        print("✅ No split fuel receipts found (or all fuel receipts have correct vehicle assignments)")
        return
    
    print(f"\nFound {len(results)} fuel receipts that are part of splits:\n")
    print(f"{'ID':<8} {'Date':<12} {'Vendor':<40} {'Amount':>12} {'Vehicle':<10} {'Split ID':<12} {'Split Cnt':<10}")
    print("-" * 140)
    
    missing_vehicle = []
    
    for row in results:
        receipt_id, date, vendor, amount, gl_code, vehicle_id, split_id, split_count = row
        
        vehicle_str = str(vehicle_id) if vehicle_id else "⚠️ MISSING"
        
        if not vehicle_id:
            missing_vehicle.append((receipt_id, date, vendor, split_id))
        
        print(f"{receipt_id:<8} {date} {vendor[:39]:<40} ${amount:>10,.2f} {vehicle_str:<10} {split_id:<12} {split_count:<10}")
    
    if missing_vehicle:
        print(f"\n⚠️  {len(missing_vehicle)} split fuel receipts missing vehicle assignment!")
        print("\nThese receipts should be reviewed:")
        for receipt_id, date, vendor, split_id in missing_vehicle[:20]:
            print(f"  - Receipt {receipt_id} ({date}): {vendor} [Split {split_id}]")


def update_fuel_gl_codes(cur, conn):
    """Update all fuel receipts to correct GL code."""
    print("\n\n" + "=" * 80)
    print("✏️ APPLYING UPDATES...")
    print("=" * 80 + "\n")
    
    # Build dynamic SQL with proper parameter placeholders
    vendor_like_clauses = []
    query_params = []
    for pattern in FUEL_VENDOR_PATTERNS:
        vendor_like_clauses.append("LOWER(vendor_name) LIKE %s")
        query_params.append(pattern)
    
    vendor_conditions_sql = " OR ".join(vendor_like_clauses)
    
    # Build proper parameter order: SET values, then WHERE patterns, then != check
    update_params = [FUEL_GL_CODE, FUEL_GL_NAME, FUEL_CATEGORY]
    update_params.extend(query_params)  # Add vendor patterns
    update_params.append(FUEL_GL_CODE)  # Add != check
    
    cur.execute(f"""
        UPDATE receipts
        SET 
            gl_account_code = %s,
            gl_account_name = %s,
            category = %s,
            verified_by_edit = TRUE,
            verified_at = NOW(),
            verified_by_user = 'auto_fuel_gl_update'
        WHERE ({vendor_conditions_sql})
          AND (gl_account_code != %s OR gl_account_code IS NULL)
    """, update_params)
    
    count = cur.rowcount
    conn.commit()
    
    print(f"✅ Updated {count} receipts successfully!")
    print(f"   GL Code: {FUEL_GL_CODE}")
    print(f"   GL Name: {FUEL_GL_NAME}")
    print(f"   Category: {FUEL_CATEGORY}")
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
    for pattern in FUEL_VENDOR_PATTERNS:
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
        prefix = "✅ " if gl_code == FUEL_GL_CODE else "   "
        
        gl_code_str = gl_code if gl_code else ""
        gl_name_str = gl_name if gl_name else ""
        category_str = category if category else ""
        
        print(f"{prefix}{vendor[:42]:<45} {gl_code_str:<12} {gl_name_str[:44]:<45} {category_str[:24]:<25} {count:>6} ${amount:>11,.2f}")


def main():
    parser = argparse.ArgumentParser(description='Auto-update fuel GL codes')
    parser.add_argument('--write', action='store_true', help='Apply updates (default is dry-run)')
    parser.add_argument('--add-vendor', type=str, help='Add a vendor pattern to search for')
    
    args = parser.parse_args()
    
    if args.add_vendor:
        FUEL_VENDOR_PATTERNS.append(f'%{args.add_vendor.lower()}%')
        print(f"Added vendor pattern: %{args.add_vendor.lower()}%\n")
    
    print("🔍 FUEL GL CODE AUTO-UPDATE")
    print("=" * 80)
    print(f"Correct GL Code: {FUEL_GL_CODE} - {FUEL_GL_NAME}")
    print(f"Target Category: {FUEL_CATEGORY}")
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
        analyze_fuel_vendors(cur)
        
        # Find misclassified receipts
        results = find_misclassified_fuel(cur)
        
        # Check split receipts for vehicle assignment
        check_split_fuel_vehicle_assignment(cur)
        
        # Breakdown by vendor
        print("\n\n📈 BREAKDOWN BY VENDOR:")
        print("-" * 80)
        
        # Build dynamic SQL with proper parameter placeholders
        vendor_like_clauses2 = []
        query_params2 = []
        for pattern in FUEL_VENDOR_PATTERNS:
            vendor_like_clauses2.append("LOWER(vendor_name) LIKE %s")
            query_params2.append(pattern)
        
        vendor_conditions_sql2 = " OR ".join(vendor_like_clauses2)
        query_params2.append(FUEL_GL_CODE)  # For the != check
        
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
        
        vendors = cur.fetchall()
        
        if vendors:
            print(f"{'Vendor':<45} {'Count':>6} {'Total Amount':>15} {'Date Range'}")
            print("-" * 80)
            
            for vendor, count, amount, first_date, last_date in vendors:
                print(f"{vendor[:44]:<45} {count:>6} ${amount:>13,.2f} {first_date} to {last_date}")
        
        # Apply updates if --write flag is set
        if args.write and results:
            update_fuel_gl_codes(cur, conn)
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
