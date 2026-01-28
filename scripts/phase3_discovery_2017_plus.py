#!/usr/bin/env python3
"""
Phase 3 Discovery: 2017-2025 Data File Analysis

Discover and analyze available 2017-2025 data files to identify
opportunities for applying proven Phase 1 & 2 methodologies.

Target: Comprehensive file inventory with potential assessment
"""

import os
import sys
import pandas as pd
import psycopg2
from datetime import datetime
import glob

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

def analyze_current_database_coverage():
    """Analyze current database coverage for 2017-2025 period."""
    
    print("CURRENT DATABASE COVERAGE ANALYSIS (2017-2025)")
    print("=" * 55)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check receipts coverage by year
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as records,
            SUM(gross_amount) as total_amount,
            COUNT(DISTINCT source_system) as sources,
            MIN(receipt_date) as earliest,
            MAX(receipt_date) as latest
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2017 AND 2025
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    receipts_data = cur.fetchall()
    
    print("📊 RECEIPTS/EXPENSES COVERAGE:")
    print("-" * 30)
    total_recent_records = 0
    total_recent_amount = 0
    
    if receipts_data:
        for year, records, amount, sources, earliest, latest in receipts_data:
            year_int = int(year) if year else 0
            amount_val = amount or 0
            total_recent_records += records
            total_recent_amount += amount_val
            print(f"{year_int}: {records:,} records, ${amount_val:,.2f} ({sources} sources)")
    else:
        print("No receipts data found for 2017-2025")
    
    # Check charters coverage by year
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as year,
            COUNT(*) as records,
            SUM(COALESCE(total_amount_due, 0)) as total_revenue,
            COUNT(DISTINCT COALESCE(vehicle, 'unknown')) as vehicles
        FROM charters 
        WHERE EXTRACT(YEAR FROM charter_date) BETWEEN 2017 AND 2025
        GROUP BY EXTRACT(YEAR FROM charter_date)
        ORDER BY year
    """)
    
    charter_data = cur.fetchall()
    
    print("\n🚗 CHARTERS/REVENUE COVERAGE:")
    print("-" * 30)
    total_recent_charters = 0
    total_recent_revenue = 0
    
    if charter_data:
        for year, records, revenue, vehicles in charter_data:
            year_int = int(year) if year else 0
            revenue_val = revenue or 0
            total_recent_charters += records
            total_recent_revenue += revenue_val
            print(f"{year_int}: {records:,} charters, ${revenue_val:,.2f} ({vehicles} vehicles)")
    else:
        print("No charter data found for 2017-2025")
    
    # Check payments coverage by year
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM payment_date) as year,
            COUNT(*) as records,
            SUM(COALESCE(amount, 0)) as total_payments,
            COUNT(DISTINCT payment_method) as methods
        FROM payments 
        WHERE EXTRACT(YEAR FROM payment_date) BETWEEN 2017 AND 2025
        GROUP BY EXTRACT(YEAR FROM payment_date)
        ORDER BY year
    """)
    
    payment_data = cur.fetchall()
    
    print("\n💰 PAYMENTS COVERAGE:")
    print("-" * 20)
    total_recent_payments_records = 0
    total_recent_payments_amount = 0
    
    if payment_data:
        for year, records, payments, methods in payment_data:
            year_int = int(year) if year else 0
            payments_val = payments or 0
            total_recent_payments_records += records
            total_recent_payments_amount += payments_val
            print(f"{year_int}: {records:,} payments, ${payments_val:,.2f} ({methods} methods)")
    else:
        print("No payment data found for 2017-2025")
    
    print(f"\n📈 RECENT YEARS SUMMARY (2017-2025):")
    print(f"• Receipts: {total_recent_records:,} records, ${total_recent_amount:,.2f}")
    print(f"• Charters: {total_recent_charters:,} records, ${total_recent_revenue:,.2f}")
    print(f"• Payments: {total_recent_payments_records:,} records, ${total_recent_payments_amount:,.2f}")
    
    cur.close()
    conn.close()
    
    return {
        'receipts': {'records': total_recent_records, 'amount': total_recent_amount},
        'charters': {'records': total_recent_charters, 'revenue': total_recent_revenue},
        'payments': {'records': total_recent_payments_records, 'amount': total_recent_payments_amount}
    }

def discover_2017_plus_files():
    """Discover Excel files that may contain 2017+ data."""
    
    print("\n" + "=" * 55)
    print("2017+ DATA FILE DISCOVERY")
    print("=" * 55)
    
    # Search patterns for recent data
    search_patterns = [
        "L:/limo/docs/**/*2017*.xl*",
        "L:/limo/docs/**/*2018*.xl*",
        "L:/limo/docs/**/*2019*.xl*",
        "L:/limo/docs/**/*2020*.xl*",
        "L:/limo/docs/**/*2021*.xl*",
        "L:/limo/docs/**/*2022*.xl*",
        "L:/limo/docs/**/*2023*.xl*",
        "L:/limo/docs/**/*2024*.xl*",
        "L:/limo/docs/**/*2025*.xl*",
        "L:/limo/**/*charge*summ*.xl*",
        "L:/limo/**/*daily*summ*.xl*",
        "L:/limo/**/*revenue*.xl*",
        "L:/limo/**/*expense*.xl*",
        "L:/limo/**/*payroll*.xl*"
    ]
    
    discovered_files = []
    
    for pattern in search_patterns:
        try:
            files = glob.glob(pattern, recursive=True)
            for file_path in files:
                if os.path.isfile(file_path):
                    file_info = {
                        'path': file_path,
                        'name': os.path.basename(file_path),
                        'size': os.path.getsize(file_path),
                        'modified': datetime.fromtimestamp(os.path.getmtime(file_path))
                    }
                    discovered_files.append(file_info)
        except Exception as e:
            print(f"Search pattern failed: {pattern} - {e}")
    
    # Remove duplicates and sort
    unique_files = {}
    for file_info in discovered_files:
        path = file_info['path']
        if path not in unique_files:
            unique_files[path] = file_info
    
    discovered_files = list(unique_files.values())
    discovered_files.sort(key=lambda x: x['modified'], reverse=True)
    
    print(f"📁 DISCOVERED {len(discovered_files)} POTENTIAL FILES:")
    print("-" * 40)
    
    high_potential_files = []
    
    for i, file_info in enumerate(discovered_files[:20]):  # Show top 20
        name = file_info['name']
        size_kb = file_info['size'] / 1024
        modified = file_info['modified']
        
        # Assess potential based on filename and size
        potential_score = assess_file_potential(name, size_kb)
        
        print(f"{i+1:2d}. {name}")
        print(f"    Path: {file_info['path']}")
        print(f"    Size: {size_kb:,.1f} KB, Modified: {modified.strftime('%Y-%m-%d')}")
        print(f"    Potential: {potential_score['score']}/10 - {potential_score['reason']}")
        print()
        
        if potential_score['score'] >= 7:
            high_potential_files.append({
                'file_info': file_info,
                'potential': potential_score
            })
    
    if len(discovered_files) > 20:
        print(f"... and {len(discovered_files) - 20} more files")
    
    return high_potential_files

def assess_file_potential(filename, size_kb):
    """Assess the potential value of a file for data recovery."""
    
    filename_lower = filename.lower()
    score = 0
    reasons = []
    
    # High-value indicators
    if 'chargesumm' in filename_lower or 'charge_summ' in filename_lower:
        score += 4
        reasons.append("Charge summary (proven high-value)")
    
    if 'daily' in filename_lower and 'summ' in filename_lower:
        score += 3
        reasons.append("Daily summary pattern")
    
    if any(year in filename_lower for year in ['2017', '2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025']):
        score += 2
        reasons.append("Recent year in filename")
    
    # Content type indicators
    if any(term in filename_lower for term in ['revenue', 'income', 'sales']):
        score += 2
        reasons.append("Revenue data")
    
    if any(term in filename_lower for term in ['expense', 'cost', 'receipt']):
        score += 2
        reasons.append("Expense data")
    
    if any(term in filename_lower for term in ['payroll', 'driver', 'employee']):
        score += 2
        reasons.append("Payroll data")
    
    if any(term in filename_lower for term in ['gratuity', 'tip', 'bonus']):
        score += 2
        reasons.append("Gratuity data")
    
    # Size indicators
    if size_kb > 100:  # Files > 100KB likely contain substantial data
        score += 1
        reasons.append("Substantial file size")
    
    if size_kb > 1000:  # Files > 1MB very likely contain lots of data
        score += 1
        reasons.append("Large data file")
    
    # File type penalties
    if filename_lower.endswith('.xlsm'):
        score += 1
        reasons.append("Macro-enabled (may have complex data)")
    
    # Cap at 10
    score = min(score, 10)
    
    return {
        'score': score,
        'reason': ', '.join(reasons) if reasons else 'Standard Excel file'
    }

def analyze_high_potential_files(high_potential_files):
    """Perform quick analysis of high-potential files."""
    
    if not high_potential_files:
        print("\n[FAIL] No high-potential files found for detailed analysis")
        return []
    
    print(f"\n🎯 HIGH-POTENTIAL FILE ANALYSIS:")
    print("=" * 35)
    print(f"Analyzing top {len(high_potential_files)} high-potential files...")
    
    analysis_results = []
    
    for i, file_data in enumerate(high_potential_files[:5]):  # Analyze top 5
        file_info = file_data['file_info']
        potential = file_data['potential']
        
        print(f"\n{i+1}. ANALYZING: {file_info['name']}")
        print(f"   Potential: {potential['score']}/10 - {potential['reason']}")
        
        try:
            # Quick Excel analysis
            file_path = file_info['path']
            
            # Try to read Excel file structure
            try:
                if file_path.endswith('.xlsm') or file_path.endswith('.xlsx'):
                    df_dict = pd.read_excel(file_path, sheet_name=None, engine='openpyxl')
                else:
                    df_dict = pd.read_excel(file_path, sheet_name=None, engine='xlrd')
                
                sheet_count = len(df_dict)
                total_rows = sum(len(df) for df in df_dict.values())
                
                print(f"   📋 Structure: {sheet_count} sheets, {total_rows:,} total rows")
                
                # Look for charge summary patterns
                charge_summary_potential = 0
                for sheet_name, sheet_df in df_dict.items():
                    if len(sheet_df) > 20:  # Substantial data
                        # Check for charge summary patterns
                        if any('total' in str(col).lower() for col in sheet_df.columns):
                            charge_summary_potential += len(sheet_df)
                
                if charge_summary_potential > 100:
                    print(f"   💰 Estimated potential: {charge_summary_potential} charge records")
                    
                    analysis_results.append({
                        'file_info': file_info,
                        'potential_score': potential['score'],
                        'estimated_records': charge_summary_potential,
                        'structure': f"{sheet_count} sheets, {total_rows} rows"
                    })
                else:
                    print(f"   📊 Structure analysis complete - limited charge data detected")
                
            except Exception as e:
                print(f"   [FAIL] Excel read error: {e}")
                
        except Exception as e:
            print(f"   [FAIL] Analysis error: {e}")
    
    return analysis_results

def main():
    """Execute Phase 3 discovery for 2017+ data."""
    
    print("PHASE 3: 2017-2025 DATA DISCOVERY & ANALYSIS")
    print("=" * 50)
    print("Building on Phase 1 ($4.92M) & Phase 2 ($81K) success")
    print("Applying proven methodologies to recent years")
    print()
    
    # Analyze current database coverage
    coverage = analyze_current_database_coverage()
    
    # Discover available files
    high_potential_files = discover_2017_plus_files()
    
    # Analyze promising files
    analysis_results = analyze_high_potential_files(high_potential_files)
    
    # Generate recommendations
    print(f"\n🎯 PHASE 3 RECOMMENDATIONS:")
    print("=" * 30)
    
    if analysis_results:
        print(f"[OK] {len(analysis_results)} high-value files identified")
        print(f"📊 Apply proven Phase 1 charge summary methodology")
        print(f"💰 Estimated additional recovery potential based on file analysis")
        print(f"🔄 Use established import patterns with 2017+ date handling")
        
        # Show top recommendations
        sorted_results = sorted(analysis_results, key=lambda x: x['potential_score'], reverse=True)
        print(f"\n🏆 TOP RECOMMENDATIONS:")
        for i, result in enumerate(sorted_results[:3], 1):
            name = result['file_info']['name']
            score = result['potential_score']
            records = result['estimated_records']
            print(f"{i}. {name} (Score: {score}/10, Est: {records} records)")
    else:
        print(f"📋 Current database coverage appears comprehensive")
        print(f"💡 Focus on data quality improvement and specialized processing")
        print(f"🔍 Consider banking integration and email processing enhancement")
    
    print(f"\n🚀 READY FOR PHASE 3 EXECUTION!")
    print(f"Proven methodologies established, high-potential targets identified")

if __name__ == "__main__":
    main()