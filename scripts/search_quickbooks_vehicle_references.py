#!/usr/bin/env python3
"""
Search for QuickBooks references related to 2012 vehicle purchases and financing
"""

import psycopg2
import os
import re
from pathlib import Path

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def search_quickbooks_references():
    print("🔍 SEARCHING FOR QUICKBOOKS VEHICLE/FINANCING REFERENCES - 2012")
    print("=" * 65)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Search QuickBooks data for vehicle-related entries in 2012
        print("📊 STEP 1: Search QuickBooks database entries for 2012 vehicles")
        print("=" * 60)
        
        # Check if we have QuickBooks tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
              AND table_name LIKE '%quickbook%' 
               OR table_name LIKE '%qb_%'
               OR table_name LIKE '%journal%'
            ORDER BY table_name
        """)
        
        qb_tables = cur.fetchall()
        
        if qb_tables:
            print(f"Found {len(qb_tables)} QuickBooks-related tables:")
            for table, in qb_tables:
                print(f"  - {table}")
            print()
            
            # Search journal entries for vehicle amounts
            if any('journal' in table[0] for table in qb_tables):
                print("🔍 Searching journal entries for vehicle purchase amounts...")
                
                vehicle_amounts = [40876.66, 40850.57, 40511.25, 44186.42]  # Key amounts
                
                for amount in vehicle_amounts:
                    cur.execute("""
                        SELECT * FROM journal 
                        WHERE ABS(COALESCE("Debit", "Credit", 0) - %s) < 1.00
                          AND "Date" LIKE '2012%'
                    """, (amount,))
                    
                    matches = cur.fetchall()
                    if matches:
                        print(f"\n💰 Found journal entries for ${amount:,.2f}:")
                        for match in matches:
                            print(f"  {match}")
                    else:
                        print(f"\n[FAIL] No journal entries found for ${amount:,.2f}")
        else:
            print("[FAIL] No QuickBooks tables found in database")
        
        print()
        
        # Search receipts for QuickBooks source references
        print("📋 STEP 2: Search existing receipts for QuickBooks source data")
        print("=" * 56)
        
        cur.execute("""
            SELECT 
                source_system,
                COUNT(*) as count,
                MIN(receipt_date) as earliest,
                MAX(receipt_date) as latest,
                SUM(gross_amount) as total_amount
            FROM receipts 
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
            GROUP BY source_system
            ORDER BY total_amount DESC
        """)
        
        receipt_sources = cur.fetchall()
        
        print("Receipt sources for 2012:")
        for source, count, earliest, latest, total in receipt_sources:
            print(f"  {source}: {count} receipts, ${float(total):,.2f} ({earliest} to {latest})")
        
        # Look for QuickBooks-specific receipts
        cur.execute("""
            SELECT receipt_date, vendor_name, description, gross_amount, source_reference
            FROM receipts 
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
              AND (
                  UPPER(source_system) LIKE '%QB%' 
                  OR UPPER(source_system) LIKE '%QUICKBOOK%'
                  OR UPPER(source_reference) LIKE '%QB%'
              )
            ORDER BY receipt_date
        """)
        
        qb_receipts = cur.fetchall()
        
        if qb_receipts:
            print(f"\nFound {len(qb_receipts)} QuickBooks receipts in 2012:")
            for date, vendor, desc, amount, ref in qb_receipts:
                print(f"  {date}: ${amount:,.2f} - {vendor} - {ref}")
        else:
            print("\n[FAIL] No QuickBooks-sourced receipts found for 2012")
        
        print()
        
        # Search for Woodridge Ford references
        print("🏦 STEP 3: Search for Woodridge Ford/Heffner references")
        print("=" * 49)
        
        vendors_to_search = ['WOODRIDGE', 'HEFFNER', 'FORD', 'VEHICLE', 'AUTO']
        
        for vendor in vendors_to_search:
            cur.execute("""
                SELECT receipt_date, vendor_name, description, gross_amount, source_system
                FROM receipts 
                WHERE EXTRACT(YEAR FROM receipt_date) = 2012
                  AND (
                      UPPER(vendor_name) LIKE %s
                      OR UPPER(description) LIKE %s
                  )
                ORDER BY receipt_date
            """, (f'%{vendor}%', f'%{vendor}%'))
            
            vendor_receipts = cur.fetchall()
            
            if vendor_receipts:
                print(f"\n🔍 Found {len(vendor_receipts)} receipts mentioning '{vendor}':")
                for date, vname, desc, amount, source in vendor_receipts:
                    print(f"  {date}: ${amount:,.2f} - {vname} ({source})")
                    if float(amount) > 30000:
                        print(f"    *** MAJOR PURCHASE ***")
        
        print()
        
        # Check for missing 2012 QuickBooks data gaps
        print("📊 STEP 4: Analyze 2012 QuickBooks data completeness")
        print("=" * 48)
        
        # Compare receipt totals by month to identify gaps
        cur.execute("""
            SELECT 
                EXTRACT(MONTH FROM receipt_date) as month,
                COUNT(*) as receipt_count,
                SUM(gross_amount) as total_amount,
                STRING_AGG(DISTINCT source_system, ', ') as sources
            FROM receipts 
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
            GROUP BY EXTRACT(MONTH FROM receipt_date)
            ORDER BY month
        """)
        
        monthly_data = cur.fetchall()
        
        print("2012 Monthly Receipt Analysis:")
        print("Month | Count | Amount      | Sources")
        print("------|-------|-------------|------------------")
        
        april_amount = 0
        for month, count, amount, sources in monthly_data:
            month_name = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][int(month)]
            print(f"{month_name:5} | {count:5} | ${float(amount):>10,.0f} | {sources}")
            
            if int(month) == 4:  # April - when vehicle purchases occurred
                april_amount = float(amount)
        
        print()
        print(f"📍 April 2012 Analysis:")
        print(f"  Receipt amount in database: ${april_amount:,.2f}")
        print(f"  Vehicle purchases identified: $122,238.48")
        print(f"  Refinancing deposit: $44,186.42")
        print(f"  Expected April total: ~$166,424.90")
        
        if april_amount < 100000:
            print(f"  [WARN] SIGNIFICANT GAP: Missing ~${166424.90 - april_amount:,.2f} in April 2012")
            print(f"     This suggests QuickBooks entries were not imported for major vehicle transactions")
        
        print()
        
        # Search for accountant references or handoff indicators
        print("👨‍💼 STEP 5: Search for accountant/handoff indicators")
        print("=" * 44)
        
        # Check for any notes about accountant handling
        cur.execute("""
            SELECT DISTINCT description, source_system, COUNT(*)
            FROM receipts 
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
              AND (
                  UPPER(description) LIKE '%ACCOUNTANT%'
                  OR UPPER(description) LIKE '%CPA%'
                  OR UPPER(description) LIKE '%BOOKKEEP%'
                  OR UPPER(description) LIKE '%PROFESSIONAL%'
                  OR UPPER(description) LIKE '%AUDIT%'
              )
            GROUP BY description, source_system
        """)
        
        accountant_refs = cur.fetchall()
        
        if accountant_refs:
            print("Found accountant-related references:")
            for desc, source, count in accountant_refs:
                print(f"  {source}: {desc} ({count} entries)")
        else:
            print("[FAIL] No explicit accountant references found in receipt descriptions")
        
        print()
        
        # Final analysis
        print("🎯 ANALYSIS SUMMARY:")
        print("=" * 18)
        print()
        
        print("POTENTIAL REASONS FOR MISSING QUICKBOOKS ENTRIES:")
        print()
        print("1. **ACCOUNTANT PROCESSING GAP**:")
        print("   - Vehicle purchases may have been handled by external accountant")
        print("   - Large transactions often require special QuickBooks treatment")
        print("   - Asset purchases vs expense entries need different accounting")
        print()
        
        print("2. **FINANCING COMPLEXITY**:")
        print("   - $44,186 refinancing deposit may need loan account setup")
        print("   - Vehicle purchases with financing require multiple QB entries")
        print("   - Asset depreciation schedules need special handling")
        print()
        
        print("3. **TIMING ISSUES**:")
        print("   - April 2012 transactions concentrated in 6-day period")
        print("   - Bulk transactions may have been batched for year-end")
        print("   - Accountant may have delayed entry pending documentation")
        print()
        
        print("4. **SYSTEM LIMITATIONS**:")
        print("   - Large amounts may have exceeded daily QB limits")
        print("   - Vehicle asset classification requires special QB setup")
        print("   - Multiple accounts (financing, assets, expenses) needed")
        print()
        
        print("📋 RECOMMENDATIONS:")
        print("=" * 16)
        print("1. 🔍 Search physical files for QB backup files from April-May 2012")
        print("2. 📞 Contact 2012 accountant for vehicle transaction handling")
        print("3. 📄 Locate original purchase agreements for QB classification")
        print("4. 🏦 Check for separate QB company file for vehicle financing")
        print("5. 📊 Review 2012 tax returns for vehicle depreciation schedules")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {str(e)}")
        raise
        
    finally:
        cur.close()
        conn.close()

def main():
    search_quickbooks_references()

if __name__ == "__main__":
    main()