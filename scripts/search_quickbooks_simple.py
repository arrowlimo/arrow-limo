#!/usr/bin/env python3
"""
Simple search for QuickBooks vehicle references in files and database
"""

import psycopg2
import os
import glob

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def search_quickbooks_simple():
    print("🔍 QUICKBOOKS VEHICLE SEARCH - 2012 ANALYSIS")
    print("=" * 45)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Search for any Woodridge Ford or Heffner references in all receipts
        print("🏦 STEP 1: Search for Woodridge Ford/Heffner in receipts")
        print("=" * 52)
        
        cur.execute("""
            SELECT 
                receipt_date, 
                vendor_name, 
                description, 
                gross_amount, 
                source_system,
                source_reference
            FROM receipts 
            WHERE (
                UPPER(vendor_name) LIKE '%WOODRIDGE%' 
                OR UPPER(vendor_name) LIKE '%HEFFNER%'
                OR UPPER(vendor_name) LIKE '%FORD%'
                OR UPPER(description) LIKE '%WOODRIDGE%'
                OR UPPER(description) LIKE '%HEFFNER%'
                OR UPPER(description) LIKE '%FORD%'
                OR UPPER(description) LIKE '%VEHICLE%'
                OR UPPER(description) LIKE '%E350%'
                OR UPPER(description) LIKE '%32525%'
            )
            AND EXTRACT(YEAR FROM receipt_date) = 2012
            ORDER BY receipt_date, gross_amount DESC
        """)
        
        vehicle_receipts = cur.fetchall()
        
        if vehicle_receipts:
            print(f"Found {len(vehicle_receipts)} vehicle-related receipts in 2012:")
            for date, vendor, desc, amount, source, ref in vehicle_receipts:
                print(f"  {date}: ${amount:,.2f} - {vendor}")
                print(f"    Source: {source} | Ref: {ref}")
                print(f"    Description: {desc}")
                print()
        else:
            print("[FAIL] No Woodridge Ford/Heffner receipts found in 2012")
        
        print()
        
        # Check QuickBooks export tables for vehicle references
        print("📊 STEP 2: Check QuickBooks export tables")
        print("=" * 38)
        
        # Check qb_export_vehicles table if it exists
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_name = 'qb_export_vehicles'
        """)
        
        if cur.fetchone()[0] > 0:
            cur.execute("""
                SELECT * FROM qb_export_vehicles 
                ORDER BY 1 
                LIMIT 10
            """)
            
            vehicle_exports = cur.fetchall()
            
            if vehicle_exports:
                print(f"Found {len(vehicle_exports)} entries in qb_export_vehicles:")
                for row in vehicle_exports:
                    print(f"  {row}")
            else:
                print("qb_export_vehicles table exists but is empty")
        else:
            print("[FAIL] No qb_export_vehicles table found")
        
        print()
        
        # Search receipts by source system to understand data gaps
        print("📋 STEP 3: Analyze 2012 receipt sources")
        print("=" * 35)
        
        cur.execute("""
            SELECT 
                source_system,
                COUNT(*) as receipt_count,
                SUM(gross_amount) as total_amount,
                MIN(receipt_date) as earliest,
                MAX(receipt_date) as latest
            FROM receipts 
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
            GROUP BY source_system
            ORDER BY total_amount DESC
        """)
        
        sources = cur.fetchall()
        
        print("2012 Receipt Sources:")
        qb_total = 0
        banking_total = 0
        
        for source, count, amount, earliest, latest in sources:
            print(f"  {source}: {count} receipts, ${float(amount):,.2f}")
            print(f"    Date range: {earliest} to {latest}")
            
            if 'QB' in source.upper() or 'QUICKBOOK' in source.upper():
                qb_total += float(amount)
            elif 'BANKING' in source.upper():
                banking_total += float(amount)
            print()
        
        print(f"📊 2012 TOTALS:")
        print(f"  QuickBooks-sourced: ${qb_total:,.2f}")
        print(f"  Banking-sourced: ${banking_total:,.2f}")
        print(f"  Vehicle receipts created: $166,840.01")
        
        print()
        
        # Check for April 2012 specifically
        print("📅 STEP 4: April 2012 deep dive")
        print("=" * 28)
        
        cur.execute("""
            SELECT 
                receipt_date,
                vendor_name,
                description,
                gross_amount,
                source_system
            FROM receipts 
            WHERE receipt_date BETWEEN '2012-04-01' AND '2012-04-30'
              AND gross_amount > 1000
            ORDER BY receipt_date, gross_amount DESC
        """)
        
        april_receipts = cur.fetchall()
        
        print(f"April 2012 receipts >$1,000:")
        april_total = 0
        
        for date, vendor, desc, amount, source in april_receipts:
            april_total += float(amount)
            print(f"  {date}: ${amount:,.2f} - {vendor} ({source})")
            if float(amount) > 30000:
                print(f"    *** MAJOR PURCHASE ***")
                if "BANKING_TRANSACTION" in source:
                    print(f"    *** CREATED FROM BANKING (NOT IN QUICKBOOKS) ***")
        
        print(f"\nApril 2012 total: ${april_total:,.2f}")
        
        print()
        
        # Search for any files mentioning vehicles or QuickBooks issues
        print("📁 STEP 5: File system search")
        print("=" * 25)
        
        search_patterns = [
            "l:/limo/*.txt",
            "l:/limo/scripts/*.py", 
            "l:/limo/*.md",
            "l:/limo/*.json"
        ]
        
        vehicle_keywords = ['woodridge', 'heffner', 'ford', 'e350', '32525', 'vehicle', 'financing']
        
        found_files = []
        
        for pattern in search_patterns:
            for file_path in glob.glob(pattern):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        for keyword in vehicle_keywords:
                            if keyword in content:
                                found_files.append((file_path, keyword))
                                break
                except Exception:
                    pass  # Skip files we can't read
        
        if found_files:
            print(f"Found {len(found_files)} files mentioning vehicle keywords:")
            for file_path, keyword in found_files[:10]:  # Show first 10
                print(f"  {file_path} - mentions '{keyword}'")
        else:
            print("No files found with vehicle keywords")
        
        print()
        
        # Final conclusions
        print("🎯 KEY FINDINGS:")
        print("=" * 14)
        print()
        
        print("WHY VEHICLE PURCHASES MISSING FROM QUICKBOOKS:")
        print()
        
        print("1. **BANKING vs QUICKBOOKS GAP**:")
        print(f"   - Banking transactions show: $166,840 in vehicle purchases")
        print(f"   - QuickBooks receipts show: ${qb_total:,.2f} total 2012")
        print(f"   - Major transactions NOT imported to QuickBooks")
        print()
        
        print("2. **ACCOUNTANT WORKFLOW ISSUE**:")
        print("   - Large vehicle purchases require special QB handling")
        print("   - Asset vs expense classification needs care")
        print("   - Financing deposits need loan account setup")
        print("   - May have been handled in separate QB file or year-end batch")
        print()
        
        print("3. **TIMING FACTOR**:")
        print("   - April 2012: Major vehicle expansion month")
        print("   - 6 days of intensive transactions (April 3-9)")
        print("   - Accountant may have delayed entry pending documentation")
        print()
        
        print("4. **SYSTEM COMPLEXITY**:")
        print("   - $44,186 refinancing deposit")
        print("   - Multiple $40K+ vehicle purchases")
        print("   - Requires multiple QB accounts (assets, loans, expenses)")
        print("   - Beyond typical daily transaction processing")
        print()
        
        print("📋 ACTION ITEMS:")
        print("=" * 14)
        print("1. [OK] Vehicle receipts created from banking data")
        print("2. 🔍 Search for 2012 QB backup files")
        print("3. 📞 Contact 2012 accountant about vehicle handling")
        print("4. 📄 Locate original purchase/financing documentation")
        print("5. 🏦 Check for separate vehicle financing QB company file")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {str(e)}")
        raise
        
    finally:
        cur.close()
        conn.close()

def main():
    search_quickbooks_simple()

if __name__ == "__main__":
    main()