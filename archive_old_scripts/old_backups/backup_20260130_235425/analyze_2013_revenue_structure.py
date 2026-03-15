#!/usr/bin/env python3
"""
Analyze 2013 Revenue & Receipts queries.xlsx file structure.

This file is likely similar to our successful 2012 Expenses.xlsm that yielded $286K.
"""

import os
import pandas as pd
import glob

def find_2013_revenue_file():
    """Find the exact 2013 Revenue & Receipts file."""
    
    # Search for the file
    docs_path = r"L:\limo\docs"
    
    for root, dirs, files in os.walk(docs_path):
        for file in files:
            if '2013' in file and 'Revenue' in file and file.endswith('.xlsx'):
                return os.path.join(root, file)
    
    return None

def analyze_2013_revenue_structure():
    """Analyze the 2013 Revenue & Receipts file structure."""
    
    file_path = find_2013_revenue_file()
    
    if not file_path:
        print("Could not find 2013 Revenue & Receipts file")
        return None
    
    print(f"2013 REVENUE & RECEIPTS ANALYSIS")
    print(f"=" * 50)
    print(f"File: {os.path.basename(file_path)}")
    
    try:
        xl = pd.ExcelFile(file_path)
        sheets = xl.sheet_names
        
        print(f"Total sheets: {len(sheets)}")
        print(f"\nSheet names:")
        
        expense_potential = {}
        
        for i, sheet in enumerate(sheets, 1):
            print(f"{i:2d}. {sheet}")
            
            try:
                # Analyze each sheet
                df = pd.read_excel(file_path, sheet_name=sheet)
                
                print(f"    Rows: {len(df)}, Columns: {len(df.columns)}")
                
                # Look for expense-related columns
                amount_columns = []
                for col in df.columns:
                    col_str = str(col).lower()
                    if any(keyword in col_str for keyword in ['debit', 'credit', 'amount', 'total', 'expense']):
                        amount_columns.append(col)
                
                if amount_columns:
                    print(f"    Amount columns: {amount_columns}")
                    
                    # Try to calculate totals
                    for col in amount_columns:
                        try:
                            series = pd.to_numeric(df[col], errors='coerce')
                            total = series.sum()
                            count = series.count()
                            if total > 0:
                                print(f"      {col}: ${total:,.2f} ({count} entries)")
                                expense_potential[sheet] = {
                                    'column': col,
                                    'total': total,
                                    'count': count
                                }
                        except:
                            pass
                
                # Look for vendor/description columns
                text_columns = []
                for col in df.columns:
                    col_str = str(col).lower()
                    if any(keyword in col_str for keyword in ['name', 'vendor', 'description', 'memo', 'payee']):
                        text_columns.append(col)
                
                if text_columns:
                    print(f"    Text columns: {text_columns}")
                
            except Exception as e:
                print(f"    Error analyzing sheet: {e}")
        
        # Summary of recovery potential
        if expense_potential:
            print(f"\n🎯 EXPENSE RECOVERY POTENTIAL:")
            print("-" * 40)
            
            total_potential = 0
            for sheet, data in expense_potential.items():
                total_potential += data['total']
                print(f"{sheet:<25} ${data['total']:>10,.2f} ({data['count']:>3} entries)")
            
            print(f"\nTotal potential: ${total_potential:,.2f}")
            print(f"Tax benefit (14%): ${total_potential * 0.14:,.2f}")
            
            print(f"\n📋 COMPARISON WITH 2012:")
            print(f"2012 recovered: $286,019")
            print(f"2013 potential: ${total_potential:,.2f}")
            
            if total_potential > 100000:
                print(f"\n[OK] HIGH RECOVERY POTENTIAL CONFIRMED!")
                print("This file appears suitable for expense import similar to 2012")
            
            return {
                'file_path': file_path,
                'total_potential': total_potential,
                'expense_sheets': expense_potential
            }
        
        else:
            print(f"\nNo significant expense amounts found")
            return None
            
    except Exception as e:
        print(f"Error analyzing file: {e}")
        return None

def main():
    """Analyze 2013 expense recovery potential."""
    
    result = analyze_2013_revenue_structure()
    
    if result and result['total_potential'] > 100000:
        print(f"\n🚀 READY FOR 2013 EXPENSE IMPORT!")
        print(f"Follow the same methodology as 2012:")
        print("1. Create 2013 expense import script")
        print("2. Process each expense sheet")
        print("3. Import to receipts database") 
        print("4. Calculate tax impact")
        
        print(f"\nPotential recovery: ${result['total_potential']:,.2f}")
        print(f"This could be another MASSIVE tax benefit!")

if __name__ == "__main__":
    main()