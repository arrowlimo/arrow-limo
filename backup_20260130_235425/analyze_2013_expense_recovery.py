#!/usr/bin/env python3
"""
Analyze 2013 Revenue & Receipts Excel file for expense recovery potential.

Based on the successful 2012 recovery of $286K, let's see what 2013 contains.
"""

import sys
import os
import pandas as pd
from decimal import Decimal
import numpy as np

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_2013_excel_file():
    """Analyze the 2013 Revenue & Receipts Excel file structure."""
    
    # Find the exact filename
    docs_path = r"L:\limo\docs"
    
    # Look for 2013 revenue file
    import glob
    files_2013 = glob.glob(os.path.join(docs_path, "*2013*Revenue*"))
    
    if not files_2013:
        print("Searching for files containing '2013' and 'Revenue'...")
        all_files = glob.glob(os.path.join(docs_path, "*.xlsx"))
        files_2013 = [f for f in all_files if '2013' in f and ('Revenue' in f or 'revenue' in f)]
    
    if not files_2013:
        print("No 2013 revenue files found. Listing all 2013 Excel files...")
        all_files = glob.glob(os.path.join(docs_path, "*.xlsx"))
        files_2013 = [f for f in all_files if '2013' in f]
        
        print("2013 Excel files found:")
        for f in files_2013:
            print(f"  {os.path.basename(f)}")
        
        if not files_2013:
            return
            
        # Use the first 2013 file for analysis
        file_path = files_2013[0]
    else:
        file_path = files_2013[0]
    
    print(f"2013 EXPENSE RECOVERY ANALYSIS")
    print(f"=" * 50)
    print(f"Analyzing: {os.path.basename(file_path)}")
    
    try:
        # Get all sheet names
        xl_file = pd.ExcelFile(file_path)
        sheet_names = xl_file.sheet_names
        
        print(f"\nSheet Count: {len(sheet_names)}")
        print(f"Sheet Names:")
        
        expense_categories = []
        potential_expense_sheets = []
        
        for i, sheet in enumerate(sheet_names, 1):
            print(f"{i:2d}. {sheet}")
            
            # Check if this looks like an expense category
            expense_keywords = [
                'fuel', 'repair', 'maintenance', 'insurance', 'bank', 'office',
                'rent', 'phone', 'utilities', 'payroll', 'advertising', 'meal',
                'lease', 'misc', 'expense', 'hosp', 'supplies'
            ]
            
            if any(keyword in sheet.lower() for keyword in expense_keywords):
                expense_categories.append(sheet)
                potential_expense_sheets.append(i)
        
        if expense_categories:
            print(f"\n🎯 POTENTIAL EXPENSE CATEGORIES FOUND:")
            for category in expense_categories:
                print(f"  - {category}")
        
        # Analyze a sample sheet to understand structure
        if sheet_names:
            sample_sheet = sheet_names[0]
            print(f"\nSAMPLE SHEET ANALYSIS: {sample_sheet}")
            print("-" * 40)
            
            df = pd.read_excel(file_path, sheet_name=sample_sheet)
            print(f"Rows: {len(df)}")
            print(f"Columns: {len(df.columns)}")
            
            print(f"\nColumn Names:")
            for col in df.columns:
                print(f"  - {col}")
            
            # Look for amount columns
            amount_columns = []
            for col in df.columns:
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in ['debit', 'credit', 'amount', 'total']):
                    amount_columns.append(col)
            
            if amount_columns:
                print(f"\nAmount Columns Found:")
                for col in amount_columns:
                    print(f"  - {col}")
                
                # Try to calculate totals
                for col in amount_columns:
                    try:
                        series = pd.to_numeric(df[col], errors='coerce')
                        total = series.sum()
                        count = series.count()
                        if total > 0:
                            print(f"  {col}: ${total:,.2f} ({count} entries)")
                    except:
                        pass
        
        # If this looks promising, estimate recovery potential
        if expense_categories or amount_columns:
            print(f"\n💰 RECOVERY POTENTIAL ESTIMATE:")
            
            # Based on 2012 success, estimate 2013 potential
            # 2012 recovered $286K from 14 categories
            category_count = len(expense_categories) if expense_categories else len(sheet_names)
            estimated_recovery = (category_count / 14) * 286000
            
            print(f"Estimated categories: {category_count}")
            print(f"Estimated recovery: ${estimated_recovery:,.2f}")
            print(f"Estimated tax benefit: ${estimated_recovery * 0.14:,.2f}")
            
            print(f"\n📋 NEXT STEPS:")
            print("1. Create 2013 expense import script")
            print("2. Process all expense category sheets")
            print("3. Import to receipts database")
            print("4. Calculate updated 2013 tax position")
        
        return {
            'file_path': file_path,
            'sheet_count': len(sheet_names),
            'expense_categories': expense_categories,
            'sample_sheet': sample_sheet if sheet_names else None
        }
        
    except Exception as e:
        print(f"Error analyzing 2013 file: {e}")
        return None

def main():
    """Analyze 2013 expense recovery potential."""
    
    print("2013 EXPENSE RECOVERY OPPORTUNITY ANALYSIS")
    print("=" * 60)
    print("Following successful 2012 recovery of $286,019...")
    
    result = analyze_2013_excel_file()
    
    if result:
        print(f"\n[OK] 2013 ANALYSIS COMPLETE")
        print(f"File contains {result['sheet_count']} sheets")
        
        if result['expense_categories']:
            print(f"Found {len(result['expense_categories'])} potential expense categories")
            print(f"This could yield similar recovery to 2012!")

if __name__ == "__main__":
    main()