#!/usr/bin/env python3
"""
Scan Excel Files for Payment and Employee Banking Information
============================================================

Analyzes the specified Excel files for:
1. Cash and credit card payment information in charge summary files
2. Employee banking/etransfer information in employee files

Files to analyze:
- E:\\2achargesummary.xls
- E:\\2chargesummary.xls  
- E:\\chargesummary.xls
- E:\\employeelistbasic.xls

Usage:
    python scripts/scan_excel_payment_files.py
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

def detect_payment_columns(df):
    """Detect columns that might contain payment information"""
    payment_patterns = [
        r'cash', r'credit', r'card', r'payment', r'method', r'type',
        r'visa', r'mastercard', r'amex', r'debit', r'interac',
        r'etransfer', r'transfer', r'bank', r'deposit'
    ]
    
    payment_cols = []
    for col in df.columns:
        col_str = str(col).lower()
        for pattern in payment_patterns:
            if re.search(pattern, col_str):
                payment_cols.append(col)
                break
    
    return payment_cols

def detect_employee_banking_columns(df):
    """Detect columns that might contain employee banking information"""
    banking_patterns = [
        r'bank', r'account', r'routing', r'transit', r'institution',
        r'etransfer', r'transfer', r'email', r'payroll', r'pay',
        r'deposit', r'direct.*deposit', r'dd'
    ]
    
    banking_cols = []
    for col in df.columns:
        col_str = str(col).lower()
        for pattern in banking_patterns:
            if re.search(pattern, col_str):
                banking_cols.append(col)
                break
    
    return banking_cols

def analyze_payment_data(df, filename):
    """Analyze payment-related data in the dataframe"""
    print(f"\n{'='*60}")
    print(f"PAYMENT ANALYSIS: {filename}")
    print(f"{'='*60}")
    
    payment_cols = detect_payment_columns(df)
    
    if not payment_cols:
        print("[FAIL] No payment-related columns detected")
        return
    
    print(f"📊 Found {len(payment_cols)} potential payment columns:")
    for col in payment_cols:
        print(f"   - {col}")
    
    # Analyze each payment column
    for col in payment_cols:
        print(f"\n🔍 Column '{col}' analysis:")
        
        # Get unique values (limiting to first 20 for readability)
        unique_vals = df[col].dropna().unique()[:20]
        print(f"   Sample values: {list(unique_vals)}")
        
        # Count non-null values
        non_null_count = df[col].count()
        print(f"   Non-null entries: {non_null_count}/{len(df)}")
        
        # Look for cash/credit patterns
        if df[col].dtype == 'object':
            cash_count = df[col].str.contains(r'cash', case=False, na=False).sum()
            credit_count = df[col].str.contains(r'credit|card|visa|mastercard', case=False, na=False).sum()
            etransfer_count = df[col].str.contains(r'transfer|etransfer', case=False, na=False).sum()
            
            if cash_count > 0:
                print(f"   💰 Cash entries: {cash_count}")
            if credit_count > 0:
                print(f"   💳 Credit card entries: {credit_count}")
            if etransfer_count > 0:
                print(f"   📧 Etransfer entries: {etransfer_count}")

def analyze_employee_banking(df, filename):
    """Analyze employee banking information"""
    print(f"\n{'='*60}")
    print(f"EMPLOYEE BANKING ANALYSIS: {filename}")
    print(f"{'='*60}")
    
    banking_cols = detect_employee_banking_columns(df)
    
    if not banking_cols:
        print("[FAIL] No banking-related columns detected")
        return
    
    print(f"🏦 Found {len(banking_cols)} potential banking columns:")
    for col in banking_cols:
        print(f"   - {col}")
    
    # Analyze each banking column
    for col in banking_cols:
        print(f"\n🔍 Column '{col}' analysis:")
        
        # Get sample values
        sample_vals = df[col].dropna().head(10).tolist()
        print(f"   Sample values: {sample_vals}")
        
        # Count non-null values
        non_null_count = df[col].count()
        print(f"   Non-null entries: {non_null_count}/{len(df)}")
        
        # Look for specific banking patterns
        if df[col].dtype == 'object':
            email_count = df[col].str.contains(r'@.*\.', case=False, na=False).sum()
            account_count = df[col].str.contains(r'\d{3,}', case=False, na=False).sum()
            
            if email_count > 0:
                print(f"   📧 Email addresses found: {email_count}")
            if account_count > 0:
                print(f"   🔢 Numeric account patterns: {account_count}")

def scan_excel_file(filepath):
    """Scan a single Excel file for payment and banking information"""
    filename = Path(filepath).name
    print(f"\n🔍 Scanning: {filename}")
    
    if not os.path.exists(filepath):
        print(f"[FAIL] File not found: {filepath}")
        return
    
    try:
        # Try to read Excel file
        xl = pd.ExcelFile(filepath)
        print(f"📋 Sheets found: {xl.sheet_names}")
        
        # Analyze each sheet
        for sheet_name in xl.sheet_names:
            print(f"\n📄 Sheet: {sheet_name}")
            
            try:
                df = pd.read_excel(filepath, sheet_name=sheet_name)
                print(f"   Dimensions: {df.shape[0]} rows × {df.shape[1]} columns")
                print(f"   Columns: {list(df.columns)}")
                
                # Determine analysis type based on filename
                if 'employee' in filename.lower():
                    analyze_employee_banking(df, f"{filename}:{sheet_name}")
                else:
                    analyze_payment_data(df, f"{filename}:{sheet_name}")
                    
            except Exception as e:
                print(f"   [FAIL] Error reading sheet '{sheet_name}': {e}")
                
    except Exception as e:
        print(f"[FAIL] Error opening file: {e}")

def main():
    """Main execution function"""
    print("🔍 EXCEL FILE PAYMENT & BANKING SCANNER")
    print("=" * 50)
    
    for filepath in FILES_TO_SCAN:
        scan_excel_file(filepath)
    
    print(f"\n[OK] Scan complete!")
    print("\n📝 SUMMARY:")
    print("- Analyzed charge summary files for cash/credit card payments")
    print("- Analyzed employee files for banking/etransfer information")
    print("- Check output above for detailed findings")

if __name__ == "__main__":
    main()