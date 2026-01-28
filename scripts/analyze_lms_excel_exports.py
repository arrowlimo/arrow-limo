#!/usr/bin/env python3
"""
LMS DATA ANALYSIS - AUDIT STATEMENT & CHARGE SUMMARY
====================================================

Analyzes the exported LMS Excel files to understand structure and reconcile
with our PostgreSQL charter and payment data.
"""

import os
import pandas as pd
import psycopg2
from datetime import datetime

# Database connection
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REMOVED***')

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def analyze_lms_excel_files():
    """Analyze the LMS Excel exports."""
    
    print("📊 LMS DATA ANALYSIS - EXCEL EXPORTS")
    print("=" * 40)
    
    # File paths
    audit_file = r"L:\limo\docs\2012-2013 excel\auditstatement.xls"
    charge_file = r"L:\limo\docs\2012-2013 excel\chargesummary.xls"
    
    # Check if files exist
    print("\n🔍 FILE AVAILABILITY CHECK:")
    print("-" * 27)
    
    files_to_analyze = []
    
    if os.path.exists(audit_file):
        print(f"   [OK] Audit Statement: {audit_file}")
        files_to_analyze.append(('audit', audit_file))
    else:
        print(f"   [FAIL] Audit Statement: File not found")
    
    if os.path.exists(charge_file):
        print(f"   [OK] Charge Summary: {charge_file}")
        files_to_analyze.append(('charge', charge_file))
    else:
        print(f"   [FAIL] Charge Summary: File not found")
    
    if not files_to_analyze:
        print("\n[WARN]  No files found to analyze!")
        return
    
    # Analyze each available file
    for file_type, file_path in files_to_analyze:
        try:
            print(f"\n📋 ANALYZING {file_type.upper()} FILE:")
            print("-" * (15 + len(file_type)))
            
            # Try to read Excel file
            try:
                # First, try to get sheet names
                xl_file = pd.ExcelFile(file_path)
                sheet_names = xl_file.sheet_names
                print(f"   Sheets found: {sheet_names}")
                
                # Analyze each sheet
                for sheet_name in sheet_names:
                    print(f"\n   📄 SHEET: {sheet_name}")
                    print("   " + "-" * (10 + len(sheet_name)))
                    
                    try:
                        # Read the sheet
                        df = pd.read_excel(file_path, sheet_name=sheet_name)
                        
                        print(f"      Rows: {len(df)}")
                        print(f"      Columns: {len(df.columns)}")
                        
                        if len(df.columns) > 0:
                            print("      Column Names:")
                            for i, col in enumerate(df.columns):
                                print(f"         {i+1}. {col}")
                        
                        # Show sample data
                        if len(df) > 0:
                            print(f"\n      Sample Data (first 3 rows):")
                            print("      " + "=" * 40)
                            
                            # Display first few rows
                            for idx in range(min(3, len(df))):
                                print(f"      Row {idx + 1}:")
                                for col in df.columns:
                                    value = df.iloc[idx][col]
                                    print(f"         {col}: {value}")
                                print()
                        
                        # Look for key LMS fields
                        print(f"      🔍 LMS Field Detection:")
                        lms_fields = {
                            'Reserve_No': ['reserve_no', 'reserve', 'reservation', 'res_no'],
                            'Account_No': ['account_no', 'account', 'acct_no', 'customer'],
                            'PU_Date': ['pu_date', 'pickup_date', 'date', 'charter_date'],
                            'Rate': ['rate', 'amount', 'charge', 'total'],
                            'Balance': ['balance', 'owing', 'outstanding'],
                            'Deposit': ['deposit', 'payment', 'paid'],
                            'Name': ['name', 'customer_name', 'client']
                        }
                        
                        detected_fields = {}
                        for lms_field, variations in lms_fields.items():
                            for col in df.columns:
                                col_lower = str(col).lower()
                                for variation in variations:
                                    if variation in col_lower:
                                        detected_fields[lms_field] = col
                                        break
                        
                        if detected_fields:
                            print("         Detected LMS Fields:")
                            for lms_field, actual_col in detected_fields.items():
                                print(f"            {lms_field} → {actual_col}")
                        else:
                            print("         No standard LMS fields detected")
                        
                    except Exception as e:
                        print(f"      [FAIL] Error reading sheet {sheet_name}: {str(e)}")
                
            except Exception as e:
                print(f"   [FAIL] Error reading Excel file: {str(e)}")
                
        except Exception as e:
            print(f"   [FAIL] Error analyzing {file_type} file: {str(e)}")
    
    # Compare with our PostgreSQL data
    print(f"\n🔄 COMPARISON WITH POSTGRESQL DATA:")
    print("-" * 37)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get 2012-2013 charter data from our system
        cur.execute("""
            SELECT 
                EXTRACT(YEAR FROM charter_date) as year,
                COUNT(*) as charter_count,
                SUM(rate) as total_revenue,
                AVG(rate) as avg_rate,
                MIN(charter_date) as earliest_date,
                MAX(charter_date) as latest_date
            FROM charters
            WHERE charter_date >= '2012-01-01' AND charter_date <= '2013-12-31'
            GROUP BY EXTRACT(YEAR FROM charter_date)
            ORDER BY year
        """)
        
        pg_data = cur.fetchall()
        
        print("   PostgreSQL Charter Data (2012-2013):")
        for year, count, revenue, avg_rate, earliest, latest in pg_data:
            print(f"      {int(year)}: {count:,} charters, ${revenue:,.2f} revenue")
            print(f"         Avg Rate: ${avg_rate:.2f}")
            print(f"         Date Range: {earliest} to {latest}")
            print()
        
        # Get reserve number patterns
        cur.execute("""
            SELECT 
                reserve_number,
                charter_date,
                rate,
                account_number
            FROM charters
            WHERE charter_date >= '2012-01-01' AND charter_date <= '2013-12-31'
            AND reserve_number IS NOT NULL
            ORDER BY charter_date
            LIMIT 10
        """)
        
        sample_reserves = cur.fetchall()
        
        print("   Sample Reserve Numbers from PostgreSQL:")
        for reserve, date, rate, account in sample_reserves:
            print(f"      {reserve} | {date} | ${rate:.2f} | Acct: {account or 'None'}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"   [FAIL] Error connecting to PostgreSQL: {str(e)}")
    
    # Recommendations
    print(f"\n💡 NEXT STEPS RECOMMENDATIONS:")
    print("-" * 30)
    print("   1. Verify Excel file column structure matches LMS export format")
    print("   2. Create import script to reconcile LMS data with PostgreSQL")
    print("   3. Focus on Reserve_No matching for charter reconciliation") 
    print("   4. Compare rates and balances to identify discrepancies")
    print("   5. Use this data to validate our existing charter records")

if __name__ == "__main__":
    # Set database environment variables
    os.environ['DB_HOST'] = 'localhost'
    os.environ['DB_NAME'] = 'almsdata'
    os.environ['DB_USER'] = 'postgres'
    os.environ['DB_PASSWORD'] = '***REMOVED***'
    
    analyze_lms_excel_files()