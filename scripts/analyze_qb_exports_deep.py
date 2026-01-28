#!/usr/bin/env python
"""
Deep analysis of QuickBooks export files - skip headers and find actual data
"""
import pandas as pd
import psycopg2
from pathlib import Path

def get_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def analyze_file_deep(filepath: Path):
    """Read file skipping typical QB headers"""
    print(f"\n{'='*80}")
    print(f"FILE: {filepath.name}")
    print(f"{'='*80}")
    
    try:
        # Read file to find where data starts
        df_raw = pd.read_excel(filepath, header=None)
        print(f"Total rows: {len(df_raw)}")
        
        # Find first row with substantial data (not just title)
        data_start = 0
        for i in range(min(20, len(df_raw))):
            row = df_raw.iloc[i]
            non_null = row.notna().sum()
            if non_null >= 3:  # Row has at least 3 columns with data
                # Check if it looks like a header row (contains common column names)
                row_str = ' '.join([str(x) for x in row if pd.notna(x)]).lower()
                if any(keyword in row_str for keyword in ['date', 'type', 'num', 'name', 'account', 'amount', 'memo', 'debit', 'credit', 'balance']):
                    data_start = i
                    print(f"Data starts at row {data_start}")
                    break
        
        # Read with proper header
        df = pd.read_excel(filepath, header=data_start)
        print(f"Data rows: {len(df)}")
        print(f"Columns: {list(df.columns[:10])}")  # First 10 columns
        
        # Show sample data
        if len(df) > 0:
            print(f"\nFirst 3 data rows:")
            for i in range(min(3, len(df))):
                print(f"  Row {i+1}:")
                for col in df.columns[:6]:  # First 6 columns
                    val = df[col].iloc[i]
                    if pd.notna(val):
                        print(f"    {col}: {val}")
        
        # Identify data type
        cols_lower = [str(c).lower() for c in df.columns]
        if 'journal' in filepath.name.lower():
            print(f"\n  📋 Type: Journal Entries")
            if 'debit' in cols_lower and 'credit' in cols_lower:
                total_dr = df['Debit'].sum() if 'Debit' in df.columns else 0
                total_cr = df['Credit'].sum() if 'Credit' in df.columns else 0
                print(f"     Total Debits: ${total_dr:,.2f}")
                print(f"     Total Credits: ${total_cr:,.2f}")
        elif 'check' in filepath.name.lower():
            print(f"\n  📋 Type: Check/Payment Details")
            if 'amount' in cols_lower:
                total = df[[c for c in df.columns if 'amount' in str(c).lower()][0]].sum()
                print(f"     Total: ${total:,.2f}")
        elif 'deposit' in filepath.name.lower():
            print(f"\n  📋 Type: Deposit Details")
        elif 'profit' in filepath.name.lower() or 'loss' in filepath.name.lower():
            print(f"\n  📋 Type: Profit & Loss Statement")
        elif 'tax' in filepath.name.lower():
            print(f"\n  📋 Type: Tax Report")
        elif 'trial' in filepath.name.lower():
            print(f"\n  📋 Type: Trial Balance")
        elif 'transaction' in filepath.name.lower():
            print(f"\n  📋 Type: Transaction Detail")
            
    except Exception as e:
        print(f"  ERROR: {e}")

def check_overlap_with_gl():
    """Check what's in general_ledger"""
    print(f"\n{'='*80}")
    print("CURRENT ALMSDATA GENERAL_LEDGER STATUS")
    print(f"{'='*80}")
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Date range
    cur.execute("SELECT MIN(date), MAX(date) FROM general_ledger WHERE date IS NOT NULL")
    min_date, max_date = cur.fetchone()
    print(f"Date range: {min_date} to {max_date}")
    
    # Total records
    cur.execute("SELECT COUNT(*) FROM general_ledger")
    total = cur.fetchone()[0]
    print(f"Total records: {total:,}")
    
    # By transaction type
    cur.execute("""
        SELECT transaction_type, COUNT(*) 
        FROM general_ledger 
        WHERE transaction_type IS NOT NULL
        GROUP BY transaction_type 
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)
    print(f"\nTop transaction types:")
    for tx_type, count in cur.fetchall():
        print(f"  {tx_type}: {count:,}")
    
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
    
    print("DEEP ANALYSIS OF QUICKBOOKS EXPORTS")
    print("Finding actual data structure in each file\n")
    
    for filepath in files:
        p = Path(filepath)
        if p.exists():
            analyze_file_deep(p)
        else:
            print(f"\n[WARN]  FILE NOT FOUND: {p.name}")
    
    check_overlap_with_gl()

if __name__ == '__main__':
    main()
