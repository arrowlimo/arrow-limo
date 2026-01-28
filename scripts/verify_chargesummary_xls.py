#!/usr/bin/env python3
"""
Verify almsdata database against chargesummary.xls report.
Parse the report properly, skipping headers.
"""

import pandas as pd
import psycopg2
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )

def main():
    print("=" * 100)
    print("CHARGESUMMARY.XLS VERIFICATION AGAINST ALMSDATA")
    print("=" * 100)
    print()
    
    xls_path = r'L:\limo\chargesummary.xls'
    
    # Read the file and look for the data
    df_raw = pd.read_excel(xls_path, sheet_name='Sheet1', header=None)
    
    # Find the row with column headers
    header_row = None
    for i in range(min(20, len(df_raw))):
        row_str = ' '.join([str(x) for x in df_raw.iloc[i].values if pd.notna(x)]).upper()
        if 'RESERVE' in row_str or 'ACCOUNT' in row_str or 'DATE' in row_str:
            header_row = i
            print(f"Found header row at index {i}")
            print(f"Headers: {df_raw.iloc[i].values}")
            break
    
    if header_row is None:
        # Try reading with different approaches
        print("\nSearching for data patterns...")
        for i in range(min(50, len(df_raw))):
            row = df_raw.iloc[i]
            non_null = row[pd.notna(row)]
            if len(non_null) > 5:
                print(f"\nRow {i}: {non_null.values}")
    else:
        # Read with proper header
        df = pd.read_excel(xls_path, sheet_name='Sheet1', header=header_row)
        
        print(f"\n{'=' * 100}")
        print("EXCEL DATA STRUCTURE")
        print('=' * 100)
        print(f"\nShape: {df.shape[0]} rows x {df.shape[1]} columns")
        print(f"\nColumns: {list(df.columns)}")
        
        # Clean column names
        df.columns = [str(col).strip() for col in df.columns]
        
        # Show sample data
        print(f"\nFirst 20 rows of data:")
        print(df.head(20).to_string())
        
        # Find numeric columns
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        if len(numeric_cols) > 0:
            print(f"\nNumeric columns: {list(numeric_cols)}")
            print(f"\nNumeric summary:")
            print(df[numeric_cols].describe())
        
        # Try to identify key columns by pattern
        possible_mappings = {
            'reserve': ['reserve', 'res', 'reservation', 'reserve_number', 'reserve #'],
            'account': ['account', 'acct', 'account_number', 'account #'],
            'date': ['date', 'charter_date', 'service_date'],
            'charge': ['charge', 'charges', 'amount', 'total'],
            'payment': ['payment', 'paid', 'payments'],
            'balance': ['balance', 'bal', 'outstanding']
        }
        
        print(f"\n{'=' * 100}")
        print("COLUMN MAPPING")
        print('=' * 100)
        
        for key, patterns in possible_mappings.items():
            for col in df.columns:
                col_lower = str(col).lower().strip()
                if any(pattern in col_lower for pattern in patterns):
                    print(f"{key.upper()}: '{col}'")
                    # Show sample values
                    sample = df[col].dropna().head(5)
                    if len(sample) > 0:
                        print(f"  Sample values: {list(sample.values)}")
                    break
        
        # Calculate totals from Excel
        print(f"\n{'=' * 100}")
        print("EXCEL TOTALS")
        print('=' * 100)
        
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if any(keyword in col_lower for keyword in ['charge', 'payment', 'balance', 'amount', 'total']):
                try:
                    total = pd.to_numeric(df[col], errors='coerce').sum()
                    count = pd.to_numeric(df[col], errors='coerce').count()
                    if total != 0 or count > 0:
                        print(f"{col}: ${total:,.2f} ({count:,} values)")
                except:
                    pass
    
    # Database comparison
    print(f"\n{'=' * 100}")
    print("DATABASE COMPARISON")
    print('=' * 100)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get comprehensive charter summary
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            COUNT(CASE WHEN total_amount_due IS NOT NULL THEN 1 END) as with_charges,
            SUM(COALESCE(total_amount_due, 0)) as total_charges,
            SUM(COALESCE(paid_amount, 0)) as total_payments,
            SUM(COALESCE(balance, 0)) as total_balance,
            MIN(charter_date) as earliest_date,
            MAX(charter_date) as latest_date
        FROM charters
    """)
    
    db_row = cur.fetchone()
    
    print(f"\nDatabase charters table:")
    print(f"  Total records: {db_row[0]:,}")
    print(f"  With charges: {db_row[1]:,}")
    print(f"  Total charges: ${db_row[2]:,.2f}")
    print(f"  Total payments: ${db_row[3]:,.2f}")
    print(f"  Total balance: ${db_row[4]:,.2f}")
    print(f"  Date range: {db_row[5]} to {db_row[6]}")
    
    # Get payment summary
    cur.execute("""
        SELECT 
            COUNT(*) as total_payments,
            SUM(amount) as total_amount
        FROM payments
    """)
    
    pmt_row = cur.fetchone()
    print(f"\nDatabase payments table:")
    print(f"  Total records: {pmt_row[0]:,}")
    print(f"  Total amount: ${pmt_row[1]:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
