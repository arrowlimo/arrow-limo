#!/usr/bin/env python3
"""
Analyze the 2012 Expenses.xlsm file with multiple sheets.

This file likely contains the missing business expenses we need to recover
for complete 2012 financial reconstruction.
"""

import sys
import os
import pandas as pd
from decimal import Decimal
import openpyxl
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_excel_file_structure(file_path):
    """Analyze the structure of the Excel file and all its sheets."""
    
    print("2012 EXPENSES.XLSM FILE ANALYSIS")
    print("=" * 50)
    
    try:
        # First, get all sheet names
        xl_file = pd.ExcelFile(file_path)
        sheet_names = xl_file.sheet_names
        
        print(f"Excel file: {file_path}")
        print(f"Total sheets found: {len(sheet_names)}")
        print()
        
        print("SHEET INVENTORY:")
        print("-" * 30)
        
        sheet_analysis = []
        
        for i, sheet_name in enumerate(sheet_names, 1):
            try:
                # Read just the first few rows to understand structure
                df = pd.read_excel(file_path, sheet_name=sheet_name, nrows=10)
                
                row_count_sample = len(df)
                col_count = len(df.columns)
                
                # Try to get actual row count (read more efficiently)
                try:
                    df_full = pd.read_excel(file_path, sheet_name=sheet_name)
                    actual_rows = len(df_full)
                except:
                    actual_rows = "Unknown (large file)"
                
                sheet_info = {
                    'sheet_name': sheet_name,
                    'columns': col_count,
                    'rows': actual_rows,
                    'sample_columns': list(df.columns)[:5]  # First 5 columns
                }
                
                sheet_analysis.append(sheet_info)
                
                print(f"{i:2d}. {sheet_name}")
                print(f"    Columns: {col_count}")
                print(f"    Rows: {actual_rows}")
                print(f"    Sample cols: {', '.join(str(col)[:20] for col in sheet_info['sample_columns'])}")
                print()
                
            except Exception as e:
                print(f"{i:2d}. {sheet_name} - ERROR: {str(e)[:50]}...")
                sheet_analysis.append({
                    'sheet_name': sheet_name,
                    'error': str(e)
                })
                print()
        
        return sheet_analysis
        
    except Exception as e:
        print(f"Error analyzing Excel file: {e}")
        return None

def analyze_potential_expense_sheets(file_path, sheet_analysis):
    """Analyze sheets that likely contain expense data."""
    
    print("EXPENSE DATA SHEET ANALYSIS")
    print("=" * 50)
    
    # Keywords that suggest expense/financial data
    expense_keywords = [
        'expense', 'cost', 'receipt', 'bill', 'payment', 'vendor',
        'fuel', 'maintenance', 'insurance', 'office', 'bank',
        'summary', 'total', 'amount', 'gst', 'tax'
    ]
    
    potential_expense_sheets = []
    
    for sheet in sheet_analysis:
        if 'error' in sheet:
            continue
            
        sheet_name = sheet['sheet_name'].lower()
        
        # Check if sheet name contains expense keywords
        is_expense_sheet = any(keyword in sheet_name for keyword in expense_keywords)
        
        if is_expense_sheet or sheet['rows'] > 50:  # Large sheets likely have data
            potential_expense_sheets.append(sheet)
    
    print(f"Found {len(potential_expense_sheets)} potential expense sheets:")
    print()
    
    detailed_analysis = []
    
    for sheet in potential_expense_sheets:
        sheet_name = sheet['sheet_name']
        
        try:
            print(f"ANALYZING: {sheet_name}")
            print("-" * 40)
            
            # Read the sheet data
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            print(f"Dimensions: {len(df)} rows × {len(df.columns)} columns")
            print(f"Column names: {list(df.columns)}")
            
            # Look for amount/dollar columns
            amount_columns = []
            for col in df.columns:
                col_str = str(col).lower()
                if any(word in col_str for word in ['amount', 'cost', 'total', 'price', '$', 'gst']):
                    amount_columns.append(col)
            
            if amount_columns:
                print(f"Amount columns found: {amount_columns}")
                
                # Calculate totals for amount columns
                for amt_col in amount_columns[:3]:  # First 3 amount columns
                    try:
                        # Convert to numeric, handling various formats
                        numeric_series = pd.to_numeric(df[amt_col], errors='coerce')
                        total = numeric_series.sum()
                        non_null_count = numeric_series.count()
                        
                        if total > 0:
                            print(f"  {amt_col}: ${total:,.2f} ({non_null_count} entries)")
                    except:
                        print(f"  {amt_col}: Could not calculate total")
            
            # Look for date columns
            date_columns = []
            for col in df.columns:
                col_str = str(col).lower()
                if any(word in col_str for word in ['date', 'when', 'time']):
                    date_columns.append(col)
            
            if date_columns:
                print(f"Date columns: {date_columns}")
            
            # Sample first few rows
            if len(df) > 0:
                print("Sample data (first 3 rows):")
                for i in range(min(3, len(df))):
                    print(f"  Row {i+1}: {dict(df.iloc[i])}")
            
            detailed_analysis.append({
                'sheet_name': sheet_name,
                'rows': len(df),
                'columns': list(df.columns),
                'amount_columns': amount_columns,
                'date_columns': date_columns,
                'data': df
            })
            
            print()
            
        except Exception as e:
            print(f"Error analyzing sheet '{sheet_name}': {e}")
            print()
    
    return detailed_analysis

def identify_missing_receipt_candidates(detailed_analysis):
    """Identify sheets that might contain missing receipt data."""
    
    print("MISSING RECEIPT RECOVERY ANALYSIS")
    print("=" * 50)
    
    # Look for patterns that suggest these are missing receipts
    receipt_candidates = []
    total_potential_value = Decimal('0')
    
    for analysis in detailed_analysis:
        sheet_name = analysis['sheet_name']
        amount_columns = analysis['amount_columns']
        
        if amount_columns and analysis['rows'] > 5:  # Has amounts and reasonable size
            
            # Calculate potential value
            df = analysis['data']
            potential_value = Decimal('0')
            
            for amt_col in amount_columns:
                try:
                    numeric_series = pd.to_numeric(df[amt_col], errors='coerce')
                    col_total = numeric_series.sum()
                    if col_total > 0:
                        potential_value += Decimal(str(col_total))
                except:
                    pass
            
            if potential_value > 0:
                receipt_candidates.append({
                    'sheet_name': sheet_name,
                    'potential_value': potential_value,
                    'row_count': analysis['rows'],
                    'amount_columns': amount_columns
                })
                
                total_potential_value += potential_value
    
    # Sort by potential value
    receipt_candidates.sort(key=lambda x: x['potential_value'], reverse=True)
    
    print(f"RECEIPT RECOVERY CANDIDATES:")
    print(f"Total potential value: ${total_potential_value:,.2f}")
    print()
    
    for candidate in receipt_candidates:
        print(f"{candidate['sheet_name']}")
        print(f"  Potential value: ${candidate['potential_value']:,.2f}")
        print(f"  Rows: {candidate['row_count']}")
        print(f"  Amount columns: {candidate['amount_columns']}")
        print()
    
    return receipt_candidates, total_potential_value

def main():
    """Main analysis function for 2012 Expenses.xlsm."""
    
    file_path = r"L:\limo\docs\2012 Expenses.xlsm"
    
    print("2012 MISSING EXPENSE DATA RECOVERY")
    print("=" * 60)
    print("Analyzing Excel file with multiple sheets to recover")
    print("missing business expenses for complete 2012 reconstruction.\n")
    
    # Check if file exists
    if not Path(file_path).exists():
        print(f"[FAIL] ERROR: File not found: {file_path}")
        return
    
    # Analyze file structure
    sheet_analysis = analyze_excel_file_structure(file_path)
    
    if not sheet_analysis:
        return
    
    # Analyze potential expense sheets
    detailed_analysis = analyze_potential_expense_sheets(file_path, sheet_analysis)
    
    # Identify missing receipt candidates
    receipt_candidates, total_value = identify_missing_receipt_candidates(detailed_analysis)
    
    # Summary
    print("RECOVERY SUMMARY")
    print("=" * 30)
    print(f"Total sheets analyzed: {len(sheet_analysis)}")
    print(f"Expense data sheets: {len(detailed_analysis)}")
    print(f"Receipt candidates: {len(receipt_candidates)}")
    print(f"Potential recovery value: ${total_value:,.2f}")
    
    if total_value > 10000:  # Significant amount
        print(f"\n🎯 SIGNIFICANT MISSING DATA FOUND!")
        print(f"This could explain the missing business expenses we identified")
        print(f"in our cash transaction analysis ($727K total with 89.6% non-payroll).")
        
        print(f"\n📋 RECOMMENDED NEXT STEPS:")
        print("1. Import the most valuable expense sheets to receipts table")
        print("2. Match these expenses to our banking transaction analysis") 
        print("3. Validate GST calculations for tax compliance")
        print("4. Update 2012 financial statements with recovered data")

if __name__ == "__main__":
    main()