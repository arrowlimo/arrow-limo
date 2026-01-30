#!/usr/bin/env python3
"""
Verify chargesummary.xls against charter_charges table.
This is a charge detail report, not a charter summary.
"""

import pandas as pd
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def main():
    print("=" * 100)
    print("CHARGESUMMARY.XLS vs CHARTER_CHARGES VERIFICATION")
    print("=" * 100)
    print()
    
    xls_path = r'L:\limo\chargesummary.xls'
    
    # Read Excel (skip total rows)
    df = pd.read_excel(xls_path, sheet_name='Sheet1', header=11)
    df.columns = [str(col).strip().replace('\n', ' ') for col in df.columns]
    df = df.dropna(how='all')
    
    # Exclude total/subtotal rows
    first_col = df.columns[0]
    df[first_col] = df[first_col].astype(str)
    df = df[~df[first_col].str.contains('Sub-Total|Total|TOTAL|Grand', case=False, na=False)].copy()
    
    # Filter to valid data
    reserve_num_col = 'Reserve  Number'
    total_col = 'Total'
    
    df['reserve_numeric'] = pd.to_numeric(df[reserve_num_col], errors='coerce')
    df = df[df['reserve_numeric'].notna()].copy()
    df['total_numeric'] = pd.to_numeric(df[total_col], errors='coerce')
    df = df[df['total_numeric'].notna()].copy()
    df = df[df['total_numeric'] < 100000].copy()
    
    excel_total = df['total_numeric'].sum()
    excel_count = len(df)
    
    print(f"EXCEL CHARGESUMMARY.XLS:")
    print(f"  Charge records: {excel_count:,}")
    print(f"  Total charges: ${excel_total:,.2f}")
    print(f"  Average charge: ${excel_total/excel_count:,.2f}")
    print(f"  Reserve number range: {int(df['reserve_numeric'].min())} to {int(df['reserve_numeric'].max())}")
    
    # Database charter_charges
    print(f"\n{'=' * 100}")
    print("DATABASE CHARTER_CHARGES TABLE:")
    print('=' * 100)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_charges,
            SUM(COALESCE(amount, 0)) as total_amount,
            MIN(created_at) as earliest_date,
            MAX(created_at) as latest_date
        FROM charter_charges
    """)
    
    row = cur.fetchone()
    
    print(f"\n  Total charge records: {row[0]:,}")
    print(f"  Total amount: ${row[1]:,.2f}")
    print(f"  Average: ${row[1]/row[0]:,.2f}")
    print(f"  Date range: {row[2]} to {row[3]}")
    
    # Comparison
    print(f"\n{'=' * 100}")
    print("COMPARISON:")
    print('=' * 100)
    
    db_total = float(row[1])
    diff = excel_total - db_total
    pct = 100 * db_total / excel_total if excel_total > 0 else 0
    
    print(f"\n  Excel total: ${excel_total:,.2f}")
    print(f"  Database total: ${row[1]:,.2f}")
    print(f"  Difference: ${diff:,.2f} ({pct:.1f}%)")
    
    if abs(diff) < 1000000:
        print(f"\n  [OK] EXCELLENT MATCH - Difference is only ${abs(diff):,.2f}")
    else:
        print(f"\n  [WARN] Difference of ${abs(diff):,.2f} needs investigation")
    
    # Check for matching by reserve number
    print(f"\n{'=' * 100}")
    print("RESERVE NUMBER VERIFICATION:")
    print('=' * 100)
    
    # Sample 10 reserves from Excel
    sample_reserves = df['reserve_numeric'].head(20).astype(int).tolist()
    
    print(f"\nChecking sample reserves from Excel:")
    for reserve_num in sample_reserves[:10]:
        excel_row = df[df['reserve_numeric'] == reserve_num].iloc[0]
        excel_amt = excel_row['total_numeric']
        
        # Check if exists in charter_charges directly by reserve_number
        cur.execute("""
            SELECT COUNT(*), SUM(COALESCE(amount, 0))
            FROM charter_charges
            WHERE reserve_number = %s
        """, (str(reserve_num).zfill(6),))
        
        db_row = cur.fetchone()
        
        if db_row and db_row[0] > 0:
            print(f"  Reserve {reserve_num}: Excel=${excel_amt:,.2f}, DB={db_row[0]} charges totaling ${float(db_row[1]):,.2f}")
        else:
            print(f"  Reserve {reserve_num}: Excel=${excel_amt:,.2f}, DB=NOT FOUND")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
