#!/usr/bin/env python3
"""
Check if Excel archive files are already in almsdata database.

Cross-reference the discovered Excel files with existing database records
to identify truly NEW data vs already imported data.
"""

import os
import sys
import psycopg2
from datetime import datetime
from decimal import Decimal

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
        port=os.getenv('DB_PORT', '5432')
    )

def analyze_existing_database_coverage():
    """Analyze what data already exists in almsdata database."""
    
    print("ALMSDATA DATABASE COVERAGE ANALYSIS")
    print("=" * 70)
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check receipts coverage by year
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_amount,
            COUNT(DISTINCT source_system) as source_systems,
            array_agg(DISTINCT source_system) as systems
        FROM receipts 
        WHERE receipt_date BETWEEN '2012-01-01' AND '2017-12-31'
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    yearly_receipts = cur.fetchall()
    
    print("\n📊 EXISTING RECEIPTS DATABASE COVERAGE (2012-2017):")
    print("-" * 60)
    print(f"{'Year':<6} {'Count':<8} {'Amount':<15} {'Sources':<10} {'Systems'}")
    print("-" * 60)
    
    for year, count, amount, source_count, systems in yearly_receipts:
        year_int = int(year)
        amount_str = f"${amount or 0:,.0f}"
        systems_str = ', '.join(systems) if systems else 'None'
        
        print(f"{year_int:<6} {count:<8,} {amount_str:<15} {source_count:<10} {systems_str[:40]}")
    
    # Check for specific Excel import patterns
    print(f"\n🔍 EXCEL IMPORT SOURCE ANALYSIS:")
    print("-" * 60)
    
    # Check for existing Excel imports
    cur.execute("""
        SELECT 
            source_system,
            source_reference,
            COUNT(*) as record_count,
            SUM(gross_amount) as total_amount
        FROM receipts 
        WHERE source_system LIKE '%Excel%' 
           OR source_reference LIKE '%Excel%'
           OR source_reference LIKE '%2012%'
           OR source_reference LIKE '%GST%'
           OR source_reference LIKE '%Reconcile%'
        GROUP BY source_system, source_reference
        ORDER BY total_amount DESC
    """)
    
    excel_imports = cur.fetchall()
    
    if excel_imports:
        print("Existing Excel-related imports found:")
        for source_system, source_ref, count, amount in excel_imports[:10]:
            source_ref_str = (source_ref or 'Unknown')[:50]
            print(f"  {source_system or 'Unknown'} | {source_ref_str} | {count} records | ${amount or 0:,.0f}")
    else:
        print("[FAIL] No Excel-related imports found in source_system/source_reference")
    
    # Check for banking data coverage
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as count,
            SUM(gross_amount) as amount
        FROM receipts 
        WHERE source_system LIKE '%banking%' 
           OR source_system LIKE '%CIBC%'
           OR source_system LIKE '%Scotia%'
           OR category IN ('bank_fees', 'banking')
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    banking_data = cur.fetchall()
    
    print(f"\n🏦 EXISTING BANKING DATA COVERAGE:")
    print("-" * 40)
    
    if banking_data:
        for year, count, amount in banking_data:
            print(f"{int(year)}: {count} records, ${amount or 0:,.0f}")
    else:
        print("[FAIL] No banking-specific data found")
    
    # Check for GST/reconciliation data
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            SUM(gross_amount) as amount,
            SUM(gst_amount) as total_gst
        FROM receipts 
        WHERE description ILIKE '%GST%' 
           OR description ILIKE '%reconcile%'
           OR category ILIKE '%gst%'
           OR source_reference ILIKE '%gst%'
    """)
    
    gst_data = cur.fetchone()
    
    print(f"\n🧾 GST/RECONCILIATION DATA:")
    print("-" * 40)
    
    if gst_data and gst_data[0] > 0:
        count, amount, gst_total = gst_data
        print(f"GST-related records: {count}")
        print(f"Total amount: ${amount or 0:,.0f}")
        print(f"Total GST: ${gst_total or 0:,.0f}")
    else:
        print("[FAIL] No GST/reconciliation data found")
    
    # Check leasing/equipment data
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            SUM(gross_amount) as amount
        FROM receipts 
        WHERE category IN ('equipment_lease', 'lease', 'leasing')
           OR description ILIKE '%lease%'
           OR description ILIKE '%equipment%'
           OR vendor_name ILIKE '%leasing%'
    """)
    
    leasing_data = cur.fetchone()
    
    print(f"\n🚗 LEASING/EQUIPMENT DATA:")
    print("-" * 40)
    
    if leasing_data and leasing_data[0] > 0:
        count, amount = leasing_data
        print(f"Leasing records: {count}")
        print(f"Total leasing expenses: ${amount or 0:,.0f}")
    else:
        print("[FAIL] No leasing/equipment data found")
    
    cur.close()
    conn.close()
    
    return yearly_receipts

def check_specific_file_overlap():
    """Check if our 'high-value' files might already be imported."""
    
    print(f"\n" + "=" * 70)
    print("SPECIFIC FILE OVERLAP ANALYSIS")
    print("=" * 70)
    
    # Files we thought were high-value
    suspected_files = [
        {
            'filename': 'Reconcile 2012 GST.xlsx',
            'potential': 290396,
            'keywords': ['GST', 'reconcile', '2012'],
            'expected_year': 2012
        },
        {
            'filename': '2012 Reconcile Cash Receipts.xlsx', 
            'potential': 216396,
            'keywords': ['cash', 'receipts', 'reconcile', '2012'],
            'expected_year': 2012
        },
        {
            'filename': '2014 Leasing Summary.xlsx',
            'potential': 170718,
            'keywords': ['leasing', 'lease', 'equipment', '2014'],
            'expected_year': 2014
        }
    ]
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("Checking for existing data that matches our 'discovered' files:")
    print("-" * 60)
    
    for file_info in suspected_files:
        filename = file_info['filename']
        potential = file_info['potential']
        keywords = file_info['keywords']
        year = file_info['expected_year']
        
        print(f"\n📋 {filename}")
        print(f"Claimed potential: ${potential:,}")
        
        # Build search query for this file's data
        keyword_conditions = []
        for keyword in keywords:
            keyword_conditions.append(f"(source_reference ILIKE '%{keyword}%' OR description ILIKE '%{keyword}%')")
        
        if keyword_conditions:
            where_clause = ' OR '.join(keyword_conditions)
            query = f"""
                SELECT 
                    COUNT(*) as matching_records,
                    SUM(gross_amount) as matching_amount,
                    array_agg(DISTINCT source_system) as sources,
                    array_agg(DISTINCT source_reference) as references
                FROM receipts 
                WHERE EXTRACT(YEAR FROM receipt_date) = {year}
                  AND ({where_clause})
            """
            
            cur.execute(query)
        else:
            cur.execute("SELECT 0, 0, NULL, NULL")
        result = cur.fetchone()
        
        if result:
            count, amount, sources, references = result
            
            if count > 0:
                print(f"[OK] FOUND EXISTING DATA:")
                print(f"   Records: {count}")
                print(f"   Amount: ${amount or 0:,.0f}")
                print(f"   Sources: {sources}")
                
                # Calculate overlap percentage
                if potential > 0 and amount:
                    overlap_pct = min(100, (float(amount) / potential) * 100)
                    print(f"   Overlap: {overlap_pct:.1f}% of claimed potential")
                    
                    if overlap_pct > 80:
                        print(f"   🚨 LIKELY DUPLICATE - File probably already imported!")
                    elif overlap_pct > 50:
                        print(f"   [WARN]  PARTIAL OVERLAP - File may be partially imported")
                    else:
                        print(f"   [OK] NEW DATA - File contains additional data")
                else:
                    print(f"   ❓ Cannot determine overlap percentage")
            else:
                print(f"[FAIL] No matching existing data found")
                print(f"   This file likely contains NEW data")
    
    cur.close()
    conn.close()

def generate_true_gap_analysis():
    """Generate analysis of true data gaps vs false positives."""
    
    print(f"\n" + "=" * 70)
    print("TRUE DATA GAP ANALYSIS")
    print("=" * 70)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get comprehensive year-by-year breakdown
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as total_records,
            SUM(gross_amount) as total_amount,
            COUNT(DISTINCT vendor_name) as unique_vendors,
            COUNT(DISTINCT category) as unique_categories,
            array_agg(DISTINCT category ORDER BY category) as categories
        FROM receipts 
        WHERE receipt_date BETWEEN '2012-01-01' AND '2017-12-31'
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    comprehensive_data = cur.fetchall()
    
    print("COMPREHENSIVE DATABASE ANALYSIS:")
    print("-" * 60)
    
    for year, records, amount, vendors, cats, categories in comprehensive_data:
        year_int = int(year)
        print(f"\n{year_int}:")
        print(f"  Records: {records:,}")
        print(f"  Amount: ${amount or 0:,.0f}")
        print(f"  Vendors: {vendors}")
        print(f"  Categories: {cats}")
        
        # Check if this year looks complete
        if records < 100:
            print(f"  🚨 SUSPICIOUS - Very few records for full year")
        elif amount and amount < 50000:
            print(f"  [WARN]  LOW AMOUNT - May be missing expense data")
        else:
            print(f"  [OK] SUBSTANTIAL DATA - Likely well covered")
    
    # Identify true gaps
    print(f"\n🎯 TRUE DATA GAPS IDENTIFIED:")
    print("-" * 40)
    
    gaps_found = False
    
    for year, records, amount, vendors, cats, categories in comprehensive_data:
        year_int = int(year)
        
        # Define thresholds for "complete" data
        min_records_threshold = 200  # Expect at least 200 expense records per year
        min_amount_threshold = 100000  # Expect at least $100K in expenses per year
        
        if records < min_records_threshold or (amount and amount < min_amount_threshold):
            gaps_found = True
            print(f"{year_int}: Potential gap - {records} records, ${amount or 0:,.0f}")
            
            # Estimate missing data
            avg_records_per_year = 1500  # Based on other years
            avg_amount_per_year = 500000  # Based on other years
            
            missing_records = max(0, avg_records_per_year - records)
            missing_amount = max(0, avg_amount_per_year - (amount or 0))
            
            print(f"         Estimated missing: {missing_records} records, ${missing_amount:,.0f}")
    
    if not gaps_found:
        print("No significant gaps found - database appears well-populated")
    
    cur.close()
    conn.close()

def main():
    """Check if Excel files are already in almsdata database."""
    
    print("CHECKING EXCEL ARCHIVE vs ALMSDATA DATABASE")
    print("=" * 80)
    print("Investigating if 'discovered' files are already imported...")
    
    # Step 1: Analyze existing database coverage
    existing_data = analyze_existing_database_coverage()
    
    # Step 2: Check specific file overlaps
    check_specific_file_overlap()
    
    # Step 3: Generate true gap analysis
    generate_true_gap_analysis()
    
    print(f"\n" + "=" * 80)
    print("🎯 CONCLUSION & RECOMMENDATIONS")
    print("=" * 80)
    
    print("Based on this analysis:")
    print("1. Check the overlap percentages above")
    print("2. Focus on files showing <50% overlap (truly new data)")
    print("3. Investigate years with suspiciously low record counts")
    print("4. Validate that our 'high-value' discoveries aren't duplicates")
    
    print(f"\n💡 KEY INSIGHT:")
    print("If files show high overlap (>80%), they're likely already imported")
    print("Focus validation efforts on genuinely NEW data sources")

if __name__ == "__main__":
    main()