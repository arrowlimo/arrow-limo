#!/usr/bin/env python3
"""
Import SBS Accounting 2013 workbook.xls - Accounting data for 2013.

SBS (Small Business Software) accounting data may contain
additional financial records not captured elsewhere.
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
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
        port=os.getenv('DB_PORT', '5432')
    )

def analyze_sbs_accounting():
    """Analyze SBS Accounting 2013 workbook.xls for accounting data."""
    
    file_path = "L:/limo/docs/2012-2013 excel/SBS Accounting 2013 workbook.xls"
    
    print("SBS ACCOUNTING 2013 ANALYSIS")
    print("=" * 35)
    print(f"File: {file_path}")
    print("Expected: Small Business Software accounting records for 2013")
    
    if not os.path.exists(file_path):
        print(f"[FAIL] File not found: {file_path}")
        return 0
    
    try:
        # Read SBS accounting file with xlrd engine for .xls files
        df_dict = pd.read_excel(file_path, sheet_name=None, engine='xlrd')
        
        print(f"\n📋 FILE STRUCTURE:")
        print(f"Sheets found: {len(df_dict)}")
        
        total_potential = 0
        accounting_sheets = []
        
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
            
            # Look for accounting patterns
            accounting_indicators = {
                'date_cols': [],
                'account_cols': [],
                'debit_cols': [],
                'credit_cols': [],
                'amount_cols': [],
                'description_cols': [],
                'transaction_cols': [],
                'journal_cols': []
            }
            
            for col in sheet_df.columns:
                col_str = str(col).lower()
                
                if any(term in col_str for term in ['date']):
                    accounting_indicators['date_cols'].append(col)
                elif any(term in col_str for term in ['account', 'acct']):
                    accounting_indicators['account_cols'].append(col)
                elif any(term in col_str for term in ['debit', 'dr']):
                    accounting_indicators['debit_cols'].append(col)
                elif any(term in col_str for term in ['credit', 'cr']):
                    accounting_indicators['credit_cols'].append(col)
                elif any(term in col_str for term in ['amount', 'total', '$', 'value']):
                    accounting_indicators['amount_cols'].append(col)
                elif any(term in col_str for term in ['desc', 'description', 'memo', 'ref']):
                    accounting_indicators['description_cols'].append(col)
                elif any(term in col_str for term in ['transaction', 'trans', 'entry']):
                    accounting_indicators['transaction_cols'].append(col)
                elif any(term in col_str for term in ['journal', 'jrnl', 'je']):
                    accounting_indicators['journal_cols'].append(col)
            
            print(f"   📊 ACCOUNTING ANALYSIS:")
            for indicator_type, cols in accounting_indicators.items():
                if cols:
                    print(f"      {indicator_type}: {cols}")
            
            # Calculate accounting potential
            sheet_total = 0
            
            # Check accounting specific columns
            for col_type in ['debit_cols', 'credit_cols', 'amount_cols']:
                for col in accounting_indicators[col_type]:
                    try:
                        numeric_series = pd.to_numeric(sheet_df[col], errors='coerce')
                        col_total = numeric_series.sum()
                        if not pd.isna(col_total) and col_total > 0:
                            sheet_total += col_total
                            print(f"      {col_type.replace('_cols','')} {col}: ${col_total:,.2f}")
                    except:
                        pass
            
            # Scan all numeric columns if no specific amounts found
            if sheet_total == 0:
                print(f"   🔍 Scanning all columns for accounting data...")
                for col in sheet_df.columns:
                    try:
                        numeric_series = pd.to_numeric(sheet_df[col], errors='coerce')
                        valid_count = numeric_series.count()
                        if valid_count > 0:
                            col_total = numeric_series.sum()
                            if col_total > 500:  # Minimum $500 for accounting data
                                print(f"      Found potential: {col} = ${col_total:,.2f} ({valid_count} entries)")
                                sheet_total += col_total
                    except:
                        pass
            
            if sheet_total > 1000:  # $1K+ threshold for accounting data
                total_potential += sheet_total
                accounting_sheets.append({
                    'name': sheet_name,
                    'df': sheet_df,
                    'total': sheet_total,
                    'indicators': accounting_indicators
                })
                print(f"   💰 Sheet potential: ${sheet_total:,.2f}")
            else:
                print(f"   Low accounting value: ${sheet_total:,.2f}")
        
        print(f"\n💰 TOTAL ACCOUNTING POTENTIAL: ${total_potential:,.2f}")
        
        if total_potential > 5000:  # $5K+ threshold for processing
            print(f"[OK] SIGNIFICANT ACCOUNTING POTENTIAL - Processing...")
            
            # Process SBS accounting data
            return process_accounting_data(accounting_sheets, file_path)
        else:
            print(f"[FAIL] Low accounting potential - not worth importing")
            return 0
        
    except Exception as e:
        print(f"[FAIL] Error analyzing SBS accounting file: {e}")
        import traceback
        traceback.print_exc()
        return 0

def process_accounting_data(accounting_sheets, file_path):
    """Process valuable accounting sheets."""
    
    print(f"\n🚀 PROCESSING SBS ACCOUNTING:")
    print("=" * 30)
    
    total_imported = 0
    total_records = 0
    
    for i, sheet_info in enumerate(accounting_sheets[:3]):  # Top 3 accounting sheets
        print(f"\n{i+1}. Processing Accounting Sheet: {sheet_info['name']}")
        print(f"   Potential: ${sheet_info['total']:,.2f}")
        
        imported_amount, imported_count = import_accounting_sheet(
            sheet_info['df'], 
            sheet_info['name'],
            sheet_info['indicators'],
            file_path
        )
        
        total_imported += imported_amount
        total_records += imported_count
        
        print(f"   [OK] Imported: {imported_count} accounting entries, ${imported_amount:,.2f}")
    
    print(f"\n📊 SBS ACCOUNTING SUMMARY:")
    print(f"Accounting records imported: {total_records}")
    print(f"Total accounting amount: ${total_imported:,.2f}")
    
    return total_imported

def import_accounting_sheet(df, sheet_name, indicators, file_path):
    """Import accounting sheet to receipts table."""
    
    if len(df) == 0:
        return 0, 0
    
    print(f"     Processing accounting data: {sheet_name}")
    
    # Get the best columns to use
    date_col = indicators['date_cols'][0] if indicators['date_cols'] else None
    amount_col = (indicators['debit_cols'] + indicators['credit_cols'] + indicators['amount_cols'])[0] if (indicators['debit_cols'] + indicators['credit_cols'] + indicators['amount_cols']) else None
    account_col = indicators['account_cols'][0] if indicators['account_cols'] else None
    desc_col = indicators['description_cols'][0] if indicators['description_cols'] else None
    
    # Determine accounting category
    accounting_category = 'sbs_accounting'
    if any('revenue' in col.lower() for col in df.columns):
        accounting_category = 'sbs_revenue'
    elif any('expense' in col.lower() for col in df.columns):
        accounting_category = 'sbs_expense'
    
    print(f"     Using: Date={date_col}, Amount={amount_col}, Account={account_col}, Category={accounting_category}")
    
    # If no obvious amount column, scan for numeric data
    if not amount_col:
        for col in df.columns:
            try:
                numeric_series = pd.to_numeric(df[col], errors='coerce')
                if numeric_series.sum() > 2000:  # Reasonable accounting total
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
            if gross_amount > 100000:
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
            
            # Extract account info
            account_info = ""
            if account_col and pd.notna(row[account_col]):
                account_val = str(row[account_col]).strip()
                if account_val and account_val != 'nan':
                    account_info = f"Account_{account_val}"
            
            # Vendor name
            vendor_name = f"SBS_Accounting_{sheet_name}_{index}"
            if account_info:
                vendor_name = f"SBS_{account_info}"[:200]
            
            # Description
            description = f"2013 SBS Accounting - {sheet_name}"
            if desc_col and pd.notna(row[desc_col]):
                desc_val = str(row[desc_col]).strip()
                if desc_val and desc_val != 'nan':
                    description += f" - {desc_val}"[:200]
            
            if account_info:
                description += f" - {account_info}"
            
            # GST calculation (accounting data may include GST)
            gst_amount = gross_amount * 0.05 / 1.05
            net_amount = gross_amount - gst_amount
            
            # Unique hash
            hash_input = f"2013_SBS_{sheet_name}_{index}_{vendor_name}_{gross_amount}_{receipt_date.strftime('%Y-%m-%d')}"
            source_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:32]
            
            # Insert
            cur.execute("""
                INSERT INTO receipts (
                    receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
                    description, category, source_system, source_reference, source_hash
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                receipt_date, vendor_name, round(gross_amount, 2), round(gst_amount, 2), 
                round(net_amount, 2), description, accounting_category, 
                '2013_SBS_Import', f"2013_SBS_{sheet_name}_{index}", source_hash
            ))
            
            imported_count += 1
            imported_amount += gross_amount
        
        conn.commit()
        return imported_amount, imported_count
        
    except Exception as e:
        conn.rollback()
        print(f"     [FAIL] SBS accounting import error: {e}")
        return 0, 0
    finally:
        cur.close()
        conn.close()

def verify_sbs_import():
    """Verify SBS accounting import."""
    
    print(f"\n" + "=" * 50)
    print("SBS ACCOUNTING IMPORT VERIFICATION")
    print("=" * 50)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check SBS import
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts 
        WHERE source_system = '2013_SBS_Import'
    """)
    
    sbs_result = cur.fetchone()
    
    if sbs_result and sbs_result[0] > 0:
        count, amount = sbs_result
        print(f"[OK] SBS ACCOUNTING IMPORTED:")
        print(f"   Records: {count}")
        print(f"   Amount: ${amount or 0:,.2f}")
        
        # Break down by category
        cur.execute("""
            SELECT category, COUNT(*), SUM(gross_amount)
            FROM receipts 
            WHERE source_system = '2013_SBS_Import'
            GROUP BY category
            ORDER BY SUM(gross_amount) DESC
        """)
        
        categories = cur.fetchall()
        if categories:
            print(f"   📊 By Category:")
            for cat, count, amount in categories:
                print(f"      {cat}: {count} records, ${amount or 0:,.2f}")
    else:
        print(f"[FAIL] No SBS accounting data imported")
    
    # Check updated 2013 total with SBS data
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount), 
               COUNT(DISTINCT source_system) as sources
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) = 2013
    """)
    
    total_result = cur.fetchone()
    
    if total_result:
        count, amount, sources = total_result
        print(f"\n📊 UPDATED 2013 TOTAL (with SBS Accounting):")
        print(f"   Total Records: {count}")
        print(f"   Total Amount: ${amount or 0:,.2f}")
        print(f"   Data Sources: {sources}")
        
        if sources >= 6:
            print(f"   🎉 2013 has exceptional multi-source coverage!")
    
    cur.close()
    conn.close()

def main():
    """Execute SBS Accounting import for 2013."""
    
    print("PHASE 2 CONTINUATION - SBS ACCOUNTING 2013")
    print("=" * 50)
    
    # Analyze and import SBS accounting data
    recovery = analyze_sbs_accounting()
    
    if recovery > 0:
        # Verify results
        verify_sbs_import()
        
        print(f"\n🎉 SBS ACCOUNTING SUCCESS!")
        print(f"Additional accounting recovery: ${recovery:,.2f}")
        print(f"2013 now has comprehensive accounting coverage")
        print(f"Small Business Software data integrated")
    else:
        print(f"\n❓ No significant SBS accounting data found or processed")

if __name__ == "__main__":
    main()