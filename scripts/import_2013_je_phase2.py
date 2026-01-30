#!/usr/bin/env python3
"""
Import Arrow 2013 JE.xlsx - Journal Entries for 2013.

Journal Entries should contain actual accounting transactions.
Estimated $75K potential for 2013 completion.
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

def analyze_journal_entries():
    """Analyze Arrow 2013 JE.xlsx for journal entry data."""
    
    file_path = "L:/limo/docs/2012-2013 excel/Arrow 2013 JE.xlsx"
    
    print("ARROW 2013 JOURNAL ENTRIES ANALYSIS")
    print("=" * 50)
    print(f"File: {file_path}")
    print("Expected: Journal entries with debit/credit transactions")
    
    if not os.path.exists(file_path):
        print(f"[FAIL] File not found: {file_path}")
        return 0
    
    try:
        # Read journal entries file
        df_dict = pd.read_excel(file_path, sheet_name=None, engine='openpyxl')
        
        print(f"\n📋 FILE STRUCTURE:")
        print(f"Sheets found: {len(df_dict)}")
        
        total_potential = 0
        valuable_sheets = []
        
        for sheet_name, sheet_df in df_dict.items():
            print(f"\n📋 Sheet: {sheet_name}")
            print(f"   Rows: {len(sheet_df)}")
            print(f"   Columns: {len(sheet_df.columns)}")
            
            if len(sheet_df) == 0:
                print("   Empty sheet - skipping")
                continue
            
            # Show sample columns
            print(f"   Columns: {list(sheet_df.columns)[:8]}...")
            
            # Look for journal entry patterns
            je_columns = {
                'date_cols': [],
                'account_cols': [],
                'debit_cols': [],
                'credit_cols': [],
                'amount_cols': [],
                'description_cols': []
            }
            
            for col in sheet_df.columns:
                col_str = str(col).lower()
                
                if any(term in col_str for term in ['date']):
                    je_columns['date_cols'].append(col)
                elif any(term in col_str for term in ['account', 'acct']):
                    je_columns['account_cols'].append(col)
                elif any(term in col_str for term in ['debit', 'dr']):
                    je_columns['debit_cols'].append(col)
                elif any(term in col_str for term in ['credit', 'cr']):
                    je_columns['credit_cols'].append(col)
                elif any(term in col_str for term in ['amount', 'total', 'value']):
                    je_columns['amount_cols'].append(col)
                elif any(term in col_str for term in ['desc', 'description', 'memo', 'ref']):
                    je_columns['description_cols'].append(col)
            
            print(f"   📊 JE ANALYSIS:")
            for col_type, cols in je_columns.items():
                if cols:
                    print(f"      {col_type}: {cols}")
            
            # Calculate potential from debit/credit columns
            sheet_total = 0
            
            # Check debit columns
            for col in je_columns['debit_cols']:
                try:
                    numeric_series = pd.to_numeric(sheet_df[col], errors='coerce')
                    col_total = numeric_series.sum()
                    if not pd.isna(col_total) and col_total > 0:
                        sheet_total += col_total
                        print(f"      Debit {col}: ${col_total:,.2f}")
                except:
                    pass
            
            # Check credit columns (don't double count if same as debit)
            for col in je_columns['credit_cols']:
                if col not in je_columns['debit_cols']:  # Avoid double counting
                    try:
                        numeric_series = pd.to_numeric(sheet_df[col], errors='coerce')
                        col_total = numeric_series.sum()
                        if not pd.isna(col_total) and col_total > 0:
                            sheet_total += col_total
                            print(f"      Credit {col}: ${col_total:,.2f}")
                    except:
                        pass
            
            # Check other amount columns
            for col in je_columns['amount_cols']:
                if col not in je_columns['debit_cols'] and col not in je_columns['credit_cols']:
                    try:
                        numeric_series = pd.to_numeric(sheet_df[col], errors='coerce')
                        col_total = numeric_series.sum()
                        if not pd.isna(col_total) and col_total > 0:
                            sheet_total += col_total
                            print(f"      Amount {col}: ${col_total:,.2f}")
                    except:
                        pass
            
            if sheet_total > 1000:
                total_potential += sheet_total
                valuable_sheets.append({
                    'name': sheet_name,
                    'df': sheet_df,
                    'total': sheet_total,
                    'je_columns': je_columns
                })
                print(f"   💰 Sheet potential: ${sheet_total:,.2f}")
            else:
                print(f"   Low value: ${sheet_total:,.2f}")
        
        print(f"\n💰 TOTAL JE POTENTIAL: ${total_potential:,.2f}")
        
        if total_potential > 5000:  # $5K+ threshold for JE
            print(f"[OK] SIGNIFICANT JE POTENTIAL - Processing...")
            
            # Process journal entries
            return process_journal_entries(valuable_sheets, file_path)
        else:
            print(f"[FAIL] Low JE potential - not worth importing")
            return 0
        
    except Exception as e:
        print(f"[FAIL] Error analyzing JE file: {e}")
        import traceback
        traceback.print_exc()
        return 0

def process_journal_entries(valuable_sheets, file_path):
    """Process valuable journal entry sheets."""
    
    print(f"\n🚀 PROCESSING JOURNAL ENTRIES:")
    print("=" * 40)
    
    total_imported = 0
    total_records = 0
    
    for i, sheet_info in enumerate(valuable_sheets[:2]):  # Top 2 JE sheets
        print(f"\n{i+1}. Processing JE Sheet: {sheet_info['name']}")
        print(f"   Potential: ${sheet_info['total']:,.2f}")
        
        imported_amount, imported_count = import_je_sheet(
            sheet_info['df'], 
            sheet_info['name'],
            sheet_info['je_columns'],
            file_path
        )
        
        total_imported += imported_amount
        total_records += imported_count
        
        print(f"   [OK] Imported: {imported_count} entries, ${imported_amount:,.2f}")
    
    print(f"\n📊 JOURNAL ENTRIES SUMMARY:")
    print(f"JE Records imported: {total_records}")
    print(f"Total JE amount: ${total_imported:,.2f}")
    
    return total_imported

def import_je_sheet(df, sheet_name, je_columns, file_path):
    """Import journal entry sheet to receipts table."""
    
    if len(df) == 0:
        return 0, 0
    
    print(f"     Processing JE data: {sheet_name}")
    
    # Get the best columns to use
    date_col = je_columns['date_cols'][0] if je_columns['date_cols'] else None
    debit_col = je_columns['debit_cols'][0] if je_columns['debit_cols'] else None
    credit_col = je_columns['credit_cols'][0] if je_columns['credit_cols'] else None
    amount_col = je_columns['amount_cols'][0] if je_columns['amount_cols'] else None
    desc_col = je_columns['description_cols'][0] if je_columns['description_cols'] else None
    account_col = je_columns['account_cols'][0] if je_columns['account_cols'] else None
    
    print(f"     Using: Date={date_col}, Debit={debit_col}, Credit={credit_col}, Amount={amount_col}")
    
    # Determine which column to use for amounts
    primary_amount_col = debit_col or credit_col or amount_col
    
    if not primary_amount_col:
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
                amount_val = pd.to_numeric(row[primary_amount_col], errors='coerce')
                if pd.isna(amount_val) or amount_val <= 0:
                    continue
                gross_amount = float(amount_val)
            except:
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
            
            # Extract account/vendor info
            vendor_name = f"JE_2013_{sheet_name}_{index}"
            if account_col and pd.notna(row[account_col]):
                account_val = str(row[account_col]).strip()
                if account_val and account_val != 'nan':
                    vendor_name = f"Account_{account_val}"[:200]
            
            # Description
            description = f"2013 Journal Entry - {sheet_name}"
            if desc_col and pd.notna(row[desc_col]):
                desc_val = str(row[desc_col]).strip()
                if desc_val and desc_val != 'nan':
                    description += f" - {desc_val}"[:200]
            
            # Add JE type info
            je_type = "debit" if debit_col and primary_amount_col == debit_col else "credit" if credit_col else "amount"
            description += f" ({je_type})"
            
            # GST calculation
            gst_amount = gross_amount * 0.05 / 1.05
            net_amount = gross_amount - gst_amount
            
            # Unique hash
            hash_input = f"2013_JE_{sheet_name}_{index}_{vendor_name}_{gross_amount}_{receipt_date.strftime('%Y-%m-%d')}"
            source_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:32]
            
            # Insert
            cur.execute("""
                INSERT INTO receipts (
                    receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
                    description, category, source_system, source_reference, source_hash
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                receipt_date, vendor_name, round(gross_amount, 2), round(gst_amount, 2), 
                round(net_amount, 2), description, 'journal_entry', 
                '2013_JE_Import', f"2013_JE_{sheet_name}_{index}", source_hash
            ))
            
            imported_count += 1
            imported_amount += gross_amount
        
        conn.commit()
        return imported_amount, imported_count
        
    except Exception as e:
        conn.rollback()
        print(f"     [FAIL] JE Import error: {e}")
        return 0, 0
    finally:
        cur.close()
        conn.close()

def verify_je_import():
    """Verify journal entry import."""
    
    print(f"\n" + "=" * 50)
    print("JOURNAL ENTRIES IMPORT VERIFICATION")
    print("=" * 50)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check JE import
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts 
        WHERE source_system = '2013_JE_Import'
    """)
    
    je_result = cur.fetchone()
    
    if je_result and je_result[0] > 0:
        count, amount = je_result
        print(f"[OK] JOURNAL ENTRIES IMPORTED:")
        print(f"   Records: {count}")
        print(f"   Amount: ${amount or 0:,.2f}")
    else:
        print(f"[FAIL] No journal entries imported")
    
    # Check 2013 total with JE addition
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount), 
               COUNT(DISTINCT source_system) as sources
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) = 2013
    """)
    
    total_result = cur.fetchone()
    
    if total_result:
        count, amount, sources = total_result
        print(f"\n📊 UPDATED 2013 TOTAL (with JE):")
        print(f"   Total Records: {count}")
        print(f"   Total Amount: ${amount or 0:,.2f}")
        print(f"   Data Sources: {sources}")
        
        if sources >= 3:
            print(f"   🎉 2013 now has diverse data sources!")
    
    cur.close()
    conn.close()

def main():
    """Execute Journal Entries import for 2013."""
    
    print("PHASE 2 CONTINUATION - 2013 JOURNAL ENTRIES")
    print("=" * 55)
    
    # Analyze and import JE data
    recovery = analyze_journal_entries()
    
    if recovery > 0:
        # Verify results
        verify_je_import()
        
        print(f"\n🎉 JOURNAL ENTRIES SUCCESS!")
        print(f"Additional JE recovery: ${recovery:,.2f}")
        print(f"2013 completion enhanced with accounting entries")
    else:
        print(f"\n❓ No significant JE data found or processed")

if __name__ == "__main__":
    main()