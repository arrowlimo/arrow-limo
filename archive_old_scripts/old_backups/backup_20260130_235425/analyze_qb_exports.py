#!/usr/bin/env python
"""
Analyze QuickBooks export files to identify data types and check if already imported to almsdata
"""
import pandas as pd
import psycopg2
from pathlib import Path
from datetime import datetime

def get_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def analyze_excel_file(filepath: Path):
    """Analyze an Excel file structure"""
    print(f"\n{'='*80}")
    print(f"FILE: {filepath.name}")
    print(f"{'='*80}")
    
    try:
        # Try reading all sheets
        xl = pd.ExcelFile(filepath)
        print(f"Sheets: {len(xl.sheet_names)}")
        
        for sheet_name in xl.sheet_names:
            print(f"\n  Sheet: '{sheet_name}'")
            df = pd.read_excel(filepath, sheet_name=sheet_name, nrows=5)
            print(f"    Rows (sample): {len(df)}")
            print(f"    Columns: {list(df.columns)}")
            
            # Show first row sample
            if len(df) > 0:
                print(f"    Sample data:")
                for col in df.columns[:5]:  # First 5 columns
                    val = df[col].iloc[0] if len(df) > 0 else 'N/A'
                    print(f"      {col}: {val}")
                    
    except Exception as e:
        print(f"  ERROR: {e}")

def check_if_data_in_almsdata(file_type: str):
    """Check if this type of data exists in almsdata"""
    conn = get_connection()
    cur = conn.cursor()
    
    checks = {
        'journal entries': "SELECT COUNT(*) FROM general_ledger WHERE transaction_type ILIKE '%journal%'",
        'checks': "SELECT COUNT(*) FROM general_ledger WHERE transaction_type ILIKE '%check%'",
        'deposits': "SELECT COUNT(*) FROM general_ledger WHERE transaction_type ILIKE '%deposit%'",
        'profit and loss': "SELECT COUNT(*) FROM general_ledger WHERE account LIKE '4%' OR account LIKE '5%' OR account LIKE '6%'",
        'tax agency': "SELECT COUNT(*) FROM general_ledger WHERE account ILIKE '%tax%' OR account ILIKE '%gst%'",
        'trial balance': "SELECT COUNT(DISTINCT account) FROM general_ledger"
    }
    
    for data_type, query in checks.items():
        if data_type.lower() in file_type.lower():
            cur.execute(query)
            count = cur.fetchone()[0]
            print(f"\n  ✓ Related data in almsdata: {count:,} records")
            break
    
    conn.close()

def main():
    files = [
        "L:\\limo\\quickbooks\\old quickbooks\\initial adjusted journal entreis.xlsx",
        "L:\\limo\\quickbooks\\old quickbooks\\initial check details.xlsx",
        "L:\\limo\\quickbooks\\old quickbooks\\initial deposts.xlsx",
        "L:\\limo\\quickbooks\\old quickbooks\\initial general journal.xlsx",
        "L:\\limo\\quickbooks\\old quickbooks\\initial journal.xlsx",
        "L:\\limo\\quickbooks\\old quickbooks\\initial profit and loss.xlsx",
        "L:\\limo\\quickbooks\\old quickbooks\\initial tax agency detail report.xlsx",
        "L:\\limo\\quickbooks\\old quickbooks\\initial transaction details.xlsx",
        "L:\\limo\\quickbooks\\old quickbooks\\initial trial balances.xlsx",
    ]
    
    print("QUICKBOOKS EXPORT FILE ANALYSIS")
    print("Checking what data exists and if it's in almsdata\n")
    
    for filepath in files:
        p = Path(filepath)
        if p.exists():
            analyze_excel_file(p)
            check_if_data_in_almsdata(p.name)
        else:
            print(f"\n[WARN]  FILE NOT FOUND: {p.name}")
    
    # Check IIF file separately
    iif_path = Path("L:\\limo\\quickbooks\\old quickbooks\\limousine.IIF")
    if iif_path.exists():
        print(f"\n{'='*80}")
        print(f"FILE: {iif_path.name} (QuickBooks IIF format)")
        print(f"{'='*80}")
        print("  IIF is QuickBooks Interchange Format - contains full company data")
        print("  Can be imported back into QuickBooks or parsed for transactions")
        print(f"  Size: {iif_path.stat().st_size:,} bytes")

if __name__ == '__main__':
    main()
