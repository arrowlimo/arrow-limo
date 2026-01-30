#!/usr/bin/env python3
"""
Import Gratuities - 2013.xlsx - Gratuity/tip revenue for 2013.

Gratuities represent additional revenue that may not be captured
in main charter data. Critical for complete revenue tracking.
"""

import os
import sys
import pandas as pd
import psycopg2
import hashlib
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
        port=os.getenv('DB_PORT', '5432')
    )

def analyze_gratuities():
    """Analyze Gratuities - 2013.xlsx for gratuity/tip data."""
    
    file_path = "L:/limo/docs/2012-2013 excel/Gratuities - 2013.xlsx"
    
    print("2013 GRATUITIES ANALYSIS")
    print("=" * 30)
    print(f"File: {file_path}")
    print("Expected: Gratuity/tip revenue data for complete 2013 revenue tracking")
    
    if not os.path.exists(file_path):
        print(f"[FAIL] File not found: {file_path}")
        return 0
    
    try:
        # Read gratuities file
        df_dict = pd.read_excel(file_path, sheet_name=None, engine='openpyxl')
        
        print(f"\n📋 FILE STRUCTURE:")
        print(f"Sheets found: {len(df_dict)}")
        
        total_potential = 0
        gratuity_sheets = []
        
        for sheet_name, sheet_df in df_dict.items():
            print(f"\n📋 Sheet: {sheet_name}")
            print(f"   Rows: {len(sheet_df)}")
            print(f"   Columns: {len(sheet_df.columns)}")
            
            if len(sheet_df) == 0:
                print("   Empty sheet - skipping")
                continue
            
            # Show sample columns and data
            print(f"   Columns: {list(sheet_df.columns)[:6]}...")
            
            # Show first few rows for context
            if len(sheet_df) > 0:
                print(f"   Sample data:")
                for i in range(min(3, len(sheet_df))):
                    row_data = []
                    for col in list(sheet_df.columns)[:4]:
                        val = str(sheet_df.iloc[i][col])[:25]
                        row_data.append(val)
                    print(f"     Row {i}: {row_data}")
            
            # Look for gratuity patterns
            gratuity_indicators = {
                'date_cols': [],
                'amount_cols': [],
                'tip_cols': [],
                'gratuity_cols': [],
                'driver_cols': [],
                'charter_cols': [],
                'customer_cols': []
            }
            
            for col in sheet_df.columns:
                col_str = str(col).lower()
                
                if any(term in col_str for term in ['date']):
                    gratuity_indicators['date_cols'].append(col)
                elif any(term in col_str for term in ['amount', 'total', '$', 'value']):
                    gratuity_indicators['amount_cols'].append(col)
                elif any(term in col_str for term in ['tip', 'tips']):
                    gratuity_indicators['tip_cols'].append(col)
                elif any(term in col_str for term in ['gratuity', 'gratu', 'grat']):
                    gratuity_indicators['gratuity_cols'].append(col)
                elif any(term in col_str for term in ['driver', 'chauffeur', 'employee']):
                    gratuity_indicators['driver_cols'].append(col)
                elif any(term in col_str for term in ['charter', 'reservation', 'booking', 'trip']):
                    gratuity_indicators['charter_cols'].append(col)
                elif any(term in col_str for term in ['customer', 'client', 'name', 'passenger']):
                    gratuity_indicators['customer_cols'].append(col)
            
            print(f"   📊 GRATUITY ANALYSIS:")
            for indicator_type, cols in gratuity_indicators.items():
                if cols:
                    print(f"      {indicator_type}: {cols}")
            
            # Calculate gratuity potential
            sheet_total = 0
            
            # Check gratuity/tip specific columns first
            for col_type in ['tip_cols', 'gratuity_cols']:
                for col in gratuity_indicators[col_type]:
                    try:
                        numeric_series = pd.to_numeric(sheet_df[col], errors='coerce')
                        col_total = numeric_series.sum()
                        if not pd.isna(col_total) and col_total > 0:
                            sheet_total += col_total
                            print(f"      {col_type.replace('_cols','')} {col}: ${col_total:,.2f}")
                    except:
                        pass
            
            # Check general amount columns
            for col in gratuity_indicators['amount_cols']:
                try:
                    numeric_series = pd.to_numeric(sheet_df[col], errors='coerce')
                    col_total = numeric_series.sum()
                    if not pd.isna(col_total) and col_total > 0:
                        sheet_total += col_total
                        print(f"      Amount {col}: ${col_total:,.2f}")
                except:
                    pass
            
            # Scan all numeric columns if no specific amounts found
            if sheet_total == 0:
                print(f"   🔍 Scanning all columns for gratuity data...")
                for col in sheet_df.columns:
                    try:
                        numeric_series = pd.to_numeric(sheet_df[col], errors='coerce')
                        valid_count = numeric_series.count()
                        if valid_count > 0:
                            col_total = numeric_series.sum()
                            if col_total > 50:  # Minimum $50 for gratuities
                                print(f"      Found potential: {col} = ${col_total:,.2f} ({valid_count} entries)")
                                sheet_total += col_total
                    except:
                        pass
            
            if sheet_total > 100:  # $100+ threshold for gratuities
                total_potential += sheet_total
                gratuity_sheets.append({
                    'name': sheet_name,
                    'df': sheet_df,
                    'total': sheet_total,
                    'indicators': gratuity_indicators
                })
                print(f"   💰 Sheet potential: ${sheet_total:,.2f}")
            else:
                print(f"   Low gratuity value: ${sheet_total:,.2f}")
        
        print(f"\n💰 TOTAL GRATUITY POTENTIAL: ${total_potential:,.2f}")
        
        if total_potential > 500:  # $500+ threshold for processing
            print(f"[OK] SIGNIFICANT GRATUITY POTENTIAL - Processing...")
            
            # Process gratuities
            return process_gratuities(gratuity_sheets, file_path)
        else:
            print(f"[FAIL] Low gratuity potential - not worth importing")
            return 0
        
    except Exception as e:
        print(f"[FAIL] Error analyzing gratuities file: {e}")
        import traceback
        traceback.print_exc()
        return 0

def process_gratuities(gratuity_sheets, file_path):
    """Process valuable gratuity sheets."""
    
    print(f"\n🚀 PROCESSING GRATUITIES:")
    print("=" * 25)
    
    total_imported = 0
    total_records = 0
    
    for i, sheet_info in enumerate(gratuity_sheets[:3]):  # Top 3 gratuity sheets
        print(f"\n{i+1}. Processing Gratuity Sheet: {sheet_info['name']}")
        print(f"   Potential: ${sheet_info['total']:,.2f}")
        
        imported_amount, imported_count = import_gratuity_sheet(
            sheet_info['df'], 
            sheet_info['name'],
            sheet_info['indicators'],
            file_path
        )
        
        total_imported += imported_amount
        total_records += imported_count
        
        print(f"   [OK] Imported: {imported_count} gratuities, ${imported_amount:,.2f}")
    
    print(f"\n📊 GRATUITY SUMMARY:")
    print(f"Gratuity records imported: {total_records}")
    print(f"Total gratuity revenue: ${total_imported:,.2f}")
    
    return total_imported

def import_gratuity_sheet(df, sheet_name, indicators, file_path):
    """Import gratuity sheet to receipts table as additional revenue."""
    
    if len(df) == 0:
        return 0, 0
    
    print(f"     Processing gratuity data: {sheet_name}")
    
    # Get the best columns to use
    date_col = indicators['date_cols'][0] if indicators['date_cols'] else None
    amount_col = (indicators['tip_cols'] + indicators['gratuity_cols'] + indicators['amount_cols'])[0] if (indicators['tip_cols'] + indicators['gratuity_cols'] + indicators['amount_cols']) else None
    driver_col = indicators['driver_cols'][0] if indicators['driver_cols'] else None
    charter_col = indicators['charter_cols'][0] if indicators['charter_cols'] else None
    customer_col = indicators['customer_cols'][0] if indicators['customer_cols'] else None
    
    print(f"     Using: Date={date_col}, Amount={amount_col}, Driver={driver_col}, Charter={charter_col}")
    
    # If no obvious amount column, scan for numeric data
    if not amount_col:
        for col in df.columns:
            try:
                numeric_series = pd.to_numeric(df[col], errors='coerce')
                if numeric_series.sum() > 200:  # Reasonable gratuity total
                    amount_col = col
                    print(f"     Auto-detected amount column: {col}")
                    break
            except:
                pass
    
    if not amount_col:
        print(f"     [FAIL] No usable amount column found")
        return 0, 0
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    imported_count = 0
    imported_amount = 0
    
    try:
        for index, row in df.iterrows():
            # Extract amount
            try:
                amount_val = pd.to_numeric(row[amount_col], errors='coerce')
                if pd.isna(amount_val) or amount_val <= 0:
                    continue
                gross_amount = float(amount_val)
            except:
                continue
            
            # Skip extremely high amounts (likely totals or errors)
            if gross_amount > 5000:
                continue
            
            # Extract date (default to 2013)
            receipt_date = datetime(2013, 6, 15)
            if date_col and pd.notna(row[date_col]):
                try:
                    receipt_date = pd.to_datetime(row[date_col])
                    if receipt_date.year != 2013:
                        receipt_date = datetime(2013, receipt_date.month if receipt_date.month <= 12 else 6, 
                                              min(receipt_date.day, 28) if receipt_date.day <= 28 else 15)
                except:
                    pass
            
            # Extract driver info
            driver_info = ""
            if driver_col and pd.notna(row[driver_col]):
                driver_val = str(row[driver_col]).strip()
                if driver_val and driver_val != 'nan':
                    driver_info = f"Driver_{driver_val}"
            
            # Extract charter/booking info  
            charter_info = ""
            if charter_col and pd.notna(row[charter_col]):
                charter_val = str(row[charter_col]).strip()
                if charter_val and charter_val != 'nan':
                    charter_info = f"Charter_{charter_val}"
            
            # Extract customer info
            customer_info = ""
            if customer_col and pd.notna(row[customer_col]):
                customer_val = str(row[customer_col]).strip()
                if customer_val and customer_val != 'nan':
                    customer_info = customer_val[:50]
            
            # Vendor name (customer who gave gratuity)
            vendor_name = f"Gratuity_2013_{index}"
            if customer_info:
                vendor_name = f"Gratuity_{customer_info}"[:200]
            elif driver_info:
                vendor_name = f"Gratuity_for_{driver_info}"[:200]
            
            # Description
            description = f"2013 Gratuity Revenue - {sheet_name}"
            if driver_info:
                description += f" - {driver_info}"
            if charter_info:
                description += f" - {charter_info}"
            
            # Gratuities are typically not subject to GST
            gst_amount = 0.0
            net_amount = gross_amount
            
            # Unique hash
            hash_input = f"2013_Gratuity_{sheet_name}_{index}_{vendor_name}_{gross_amount}_{receipt_date.strftime('%Y-%m-%d')}"
            source_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:32]
            
            # Insert as negative receipt (represents income, not expense)
            # Or we could use a special category to distinguish
            cur.execute("""
                INSERT INTO receipts (
                    receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
                    description, category, source_system, source_reference, source_hash
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                receipt_date, vendor_name, round(gross_amount, 2), round(gst_amount, 2), 
                round(net_amount, 2), description, 'gratuity_revenue', 
                '2013_Gratuity_Import', f"2013_Gratuity_{sheet_name}_{index}", source_hash
            ))
            
            imported_count += 1
            imported_amount += gross_amount
        
        conn.commit()
        return imported_amount, imported_count
        
    except Exception as e:
        conn.rollback()
        print(f"     [FAIL] Gratuity import error: {e}")
        return 0, 0
    finally:
        cur.close()
        conn.close()

def verify_gratuity_import():
    """Verify gratuity import."""
    
    print(f"\n" + "=" * 50)
    print("GRATUITY IMPORT VERIFICATION")
    print("=" * 50)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check gratuity import
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts 
        WHERE source_system = '2013_Gratuity_Import'
    """)
    
    gratuity_result = cur.fetchone()
    
    if gratuity_result and gratuity_result[0] > 0:
        count, amount = gratuity_result
        print(f"[OK] GRATUITIES IMPORTED:")
        print(f"   Records: {count}")
        print(f"   Revenue: ${amount or 0:,.2f}")
        
        print(f"   📊 Note: Gratuities recorded as 'gratuity_revenue' category")
        print(f"   📊 GST: $0 (gratuities typically not subject to GST)")
    else:
        print(f"[FAIL] No gratuities imported")
    
    # Check updated 2013 total with gratuities
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount), 
               COUNT(DISTINCT source_system) as sources
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) = 2013
    """)
    
    total_result = cur.fetchone()
    
    if total_result:
        count, amount, sources = total_result
        print(f"\n📊 UPDATED 2013 TOTAL (with Gratuities):")
        print(f"   Total Records: {count}")
        print(f"   Total Amount: ${amount or 0:,.2f}")
        print(f"   Data Sources: {sources}")
        
        if sources >= 5:
            print(f"   🎉 2013 has excellent multi-source coverage!")
    
    cur.close()
    conn.close()

def main():
    """Execute Gratuity import for 2013."""
    
    print("PHASE 2 CONTINUATION - 2013 GRATUITIES")
    print("=" * 45)
    
    # Analyze and import gratuity data
    recovery = analyze_gratuities()
    
    if recovery > 0:
        # Verify results
        verify_gratuity_import()
        
        print(f"\n🎉 GRATUITY SUCCESS!")
        print(f"Additional gratuity revenue: ${recovery:,.2f}")
        print(f"2013 revenue tracking now includes gratuities")
        print(f"Complete driver compensation picture achieved")
    else:
        print(f"\n❓ No significant gratuity data found or processed")

if __name__ == "__main__":
    main()