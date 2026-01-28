#!/usr/bin/env python3
"""
Enhanced Excel Scanner with Content Analysis
===========================================

Analyzes Excel files with potential header/formatting issues to find:
1. Cash and credit card payment information
2. Employee banking/etransfer information

This version reads multiple header rows and examines cell content directly.
"""

import pandas as pd
import os
import re
from pathlib import Path

# Target files
FILES_TO_SCAN = [
    r"E:\2achargesummary.xls",
    r"E:\2chargesummary.xls", 
    r"E:\chargesummary.xls",
    r"E:\employeelistbasic.xls"
]

def find_payment_keywords_in_data(df):
    """Search for payment-related keywords in all cell data"""
    payment_keywords = ['cash', 'credit', 'card', 'visa', 'mastercard', 'amex', 
                       'debit', 'interac', 'etransfer', 'transfer', 'payment']
    
    found_payments = {}
    
    # Convert all data to string and search
    for col_idx, col in enumerate(df.columns):
        for row_idx in range(len(df)):
            cell_value = str(df.iloc[row_idx, col_idx]).lower()
            if pd.notna(df.iloc[row_idx, col_idx]) and cell_value != 'nan':
                for keyword in payment_keywords:
                    if keyword in cell_value:
                        if keyword not in found_payments:
                            found_payments[keyword] = []
                        found_payments[keyword].append({
                            'row': row_idx,
                            'col': col_idx, 
                            'col_name': col,
                            'value': df.iloc[row_idx, col_idx]
                        })
    
    return found_payments

def find_banking_keywords_in_data(df):
    """Search for banking-related keywords in all cell data"""
    banking_keywords = ['bank', 'account', 'routing', 'transit', 'institution',
                       'etransfer', 'transfer', 'payroll', 'direct deposit', 'dd',
                       'email', '@']
    
    found_banking = {}
    
    # Convert all data to string and search
    for col_idx, col in enumerate(df.columns):
        for row_idx in range(len(df)):
            cell_value = str(df.iloc[row_idx, col_idx]).lower()
            if pd.notna(df.iloc[row_idx, col_idx]) and cell_value != 'nan':
                # Special handling for email patterns
                if '@' in cell_value and '.' in cell_value:
                    if 'email' not in found_banking:
                        found_banking['email'] = []
                    found_banking['email'].append({
                        'row': row_idx,
                        'col': col_idx,
                        'col_name': col,
                        'value': df.iloc[row_idx, col_idx]
                    })
                
                for keyword in banking_keywords:
                    if keyword != '@' and keyword in cell_value:
                        if keyword not in found_banking:
                            found_banking[keyword] = []
                        found_banking[keyword].append({
                            'row': row_idx,
                            'col': col_idx,
                            'col_name': col,
                            'value': df.iloc[row_idx, col_idx]
                        })
    
    return found_banking

def analyze_excel_structure(filepath):
    """Analyze Excel file structure and content"""
    filename = Path(filepath).name
    print(f"\n{'='*70}")
    print(f"ANALYZING: {filename}")
    print(f"{'='*70}")
    
    if not os.path.exists(filepath):
        print(f"[FAIL] File not found: {filepath}")
        return
    
    try:
        # Read file with different strategies
        xl = pd.ExcelFile(filepath)
        
        for sheet_name in xl.sheet_names:
            print(f"\n📄 Sheet: {sheet_name}")
            
            # Try reading with different header strategies
            strategies = [
                {'header': None},  # No header
                {'header': 0},     # First row as header
                {'header': 1},     # Second row as header
                {'header': 2},     # Third row as header
            ]
            
            best_df = None
            best_strategy = None
            
            for i, strategy in enumerate(strategies):
                try:
                    df = pd.read_excel(filepath, sheet_name=sheet_name, **strategy)
                    
                    # Check if this gives us better column names
                    if i == 0 or any('Unnamed' not in str(col) for col in df.columns):
                        best_df = df
                        best_strategy = f"Strategy {i+1}: {strategy}"
                        if i > 0:  # Found better headers
                            break
                            
                except Exception as e:
                    continue
            
            if best_df is None:
                print("   [FAIL] Could not read sheet data")
                continue
                
            print(f"   📊 Best reading strategy: {best_strategy}")
            print(f"   📏 Dimensions: {best_df.shape[0]} rows × {best_df.shape[1]} columns")
            
            # Show sample column names
            sample_cols = list(best_df.columns)[:10]
            print(f"   📋 Sample columns: {sample_cols}")
            
            # Show first few rows of data (non-empty cells)
            print(f"\n   🔍 Sample data from first 5 rows:")
            for row_idx in range(min(5, len(best_df))):
                row_data = []
                for col_idx in range(min(10, len(best_df.columns))):
                    cell = best_df.iloc[row_idx, col_idx]
                    if pd.notna(cell) and str(cell).strip() != '':
                        row_data.append(f"Col{col_idx}: {cell}")
                if row_data:
                    print(f"     Row {row_idx}: {' | '.join(row_data)}")
            
            # Search for payment keywords
            if 'employee' not in filename.lower():
                print(f"\n   💰 PAYMENT KEYWORD SEARCH:")
                payment_findings = find_payment_keywords_in_data(best_df)
                
                if payment_findings:
                    for keyword, occurrences in payment_findings.items():
                        print(f"     🔍 '{keyword}' found {len(occurrences)} times:")
                        for occ in occurrences[:5]:  # Show first 5 occurrences
                            print(f"        Row {occ['row']}, Col {occ['col']}: {occ['value']}")
                        if len(occurrences) > 5:
                            print(f"        ... and {len(occurrences) - 5} more")
                else:
                    print("     [FAIL] No payment keywords found")
            
            # Search for banking keywords  
            else:
                print(f"\n   🏦 BANKING KEYWORD SEARCH:")
                banking_findings = find_banking_keywords_in_data(best_df)
                
                if banking_findings:
                    for keyword, occurrences in banking_findings.items():
                        print(f"     🔍 '{keyword}' found {len(occurrences)} times:")
                        for occ in occurrences[:5]:  # Show first 5 occurrences
                            print(f"        Row {occ['row']}, Col {occ['col']}: {occ['value']}")
                        if len(occurrences) > 5:
                            print(f"        ... and {len(occurrences) - 5} more")
                else:
                    print("     [FAIL] No banking keywords found")
                    
    except Exception as e:
        print(f"[FAIL] Error analyzing file: {e}")

def main():
    """Main execution function"""
    print("🔍 ENHANCED EXCEL PAYMENT & BANKING SCANNER")
    print("=" * 60)
    print("Scanning for:")
    print("- Cash, credit card, and payment method information")
    print("- Employee banking and etransfer details")
    print("- Email addresses and account information")
    
    for filepath in FILES_TO_SCAN:
        analyze_excel_structure(filepath)
    
    print(f"\n[OK] Enhanced scan complete!")

if __name__ == "__main__":
    main()