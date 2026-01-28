#!/usr/bin/env python3
"""
Find and analyze 2013 Excel files for expense recovery.
"""

import os
import glob
import pandas as pd

def find_2013_files():
    """Find all 2013 Excel files with full paths."""
    
    docs_path = r"L:\limo\docs"
    
    # Search for all Excel files
    excel_files = []
    for root, dirs, files in os.walk(docs_path):
        for file in files:
            if file.endswith(('.xlsx', '.xlsm', '.xls')) and '2013' in file:
                full_path = os.path.join(root, file)
                excel_files.append(full_path)
    
    return excel_files

def analyze_excel_structure(file_path):
    """Analyze Excel file structure."""
    
    try:
        xl = pd.ExcelFile(file_path)
        sheets = xl.sheet_names
        
        print(f"\nFile: {os.path.basename(file_path)}")
        print(f"Sheets: {len(sheets)}")
        
        # Look for expense-related sheets
        expense_sheets = []
        for sheet in sheets:
            sheet_lower = sheet.lower()
            expense_keywords = ['fuel', 'repair', 'maintenance', 'insurance', 'bank', 'office', 
                              'rent', 'phone', 'utilities', 'payroll', 'advertising', 'meal',
                              'lease', 'misc', 'expense', 'hosp', 'supplies', 'cost']
            
            if any(keyword in sheet_lower for keyword in expense_keywords):
                expense_sheets.append(sheet)
        
        if expense_sheets:
            print(f"Expense sheets found: {len(expense_sheets)}")
            for sheet in expense_sheets[:5]:  # Show first 5
                print(f"  - {sheet}")
            if len(expense_sheets) > 5:
                print(f"  ... and {len(expense_sheets) - 5} more")
        
        # Analyze first sheet for structure
        if sheets:
            sample_sheet = sheets[0]
            try:
                df = pd.read_excel(file_path, sheet_name=sample_sheet, nrows=10)
                
                # Look for amount columns
                amount_cols = []
                for col in df.columns:
                    col_str = str(col).lower()
                    if any(keyword in col_str for keyword in ['debit', 'credit', 'amount', 'total']):
                        amount_cols.append(col)
                
                if amount_cols:
                    print(f"Amount columns: {amount_cols}")
                    
            except Exception as e:
                print(f"  Could not analyze sample sheet: {e}")
        
        return {
            'path': file_path,
            'sheets': len(sheets),
            'expense_sheets': expense_sheets,
            'has_amounts': len(amount_cols) > 0 if 'amount_cols' in locals() else False
        }
        
    except Exception as e:
        print(f"\nError analyzing {os.path.basename(file_path)}: {e}")
        return None

def main():
    """Find and analyze all 2013 Excel files."""
    
    print("2013 EXCEL EXPENSE RECOVERY ANALYSIS")
    print("=" * 50)
    
    files_2013 = find_2013_files()
    
    print(f"Found {len(files_2013)} Excel files containing '2013'")
    
    promising_files = []
    
    for file_path in files_2013:
        result = analyze_excel_structure(file_path)
        if result and (result['expense_sheets'] or result['has_amounts']):
            promising_files.append(result)
    
    print(f"\n🎯 PROMISING FILES FOR EXPENSE RECOVERY:")
    print("=" * 50)
    
    for i, file_info in enumerate(promising_files, 1):
        print(f"{i}. {os.path.basename(file_info['path'])}")
        print(f"   Sheets: {file_info['sheets']}")
        print(f"   Expense sheets: {len(file_info['expense_sheets'])}")
        if file_info['expense_sheets']:
            print(f"   Categories: {', '.join(file_info['expense_sheets'][:3])}")
    
    if promising_files:
        print(f"\n[OK] NEXT STEPS:")
        print("1. Create import scripts for top files")
        print("2. Process expense categories similar to 2012")
        print("3. Potentially recover hundreds of thousands more!")
        
        # Estimate total recovery potential
        total_estimated = len(promising_files) * 200000  # Conservative estimate
        print(f"\nEstimated total recovery potential: ${total_estimated:,}")
        print(f"Estimated tax benefit: ${total_estimated * 0.14:,}")

if __name__ == "__main__":
    main()