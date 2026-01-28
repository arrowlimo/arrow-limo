#!/usr/bin/env python3
"""
Detailed verification of chargesummary.xls against almsdata.
Compare reserve numbers, dates, and totals.
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
    print("CHARGESUMMARY.XLS DETAILED VERIFICATION")
    print("=" * 100)
    print()
    
    xls_path = r'L:\limo\chargesummary.xls'
    
    # Read with proper header (row 11)
    df = pd.read_excel(xls_path, sheet_name='Sheet1', header=11)
    
    # Clean up column names
    df.columns = [str(col).strip().replace('\n', ' ') for col in df.columns]
    
    # Remove completely empty rows
    df = df.dropna(how='all')
    
    # Identify key columns
    reserve_num_col = 'Reserve  Number'
    reserve_date_col = 'Reserve  Date'
    total_col = 'Total'
    
    # CRITICAL: Exclude rows that contain totals/subtotals
    # Look for "Sub-Total", "Total", "Grand Total" etc. in the date column or reserve column
    if reserve_date_col in df.columns:
        df[reserve_date_col] = df[reserve_date_col].astype(str)
        df = df[~df[reserve_date_col].str.contains('Total|total|TOTAL', case=False, na=False)].copy()
    
    if reserve_num_col in df.columns:
        df[reserve_num_col] = df[reserve_num_col].astype(str)
        df = df[~df[reserve_num_col].str.contains('Total|total|TOTAL', case=False, na=False)].copy()
    
    # Also check the first column for total indicators
    first_col = df.columns[0]
    df[first_col] = df[first_col].astype(str)
    df = df[~df[first_col].str.contains('Sub-Total|Total|total|TOTAL|Grand Total', case=False, na=False)].copy()
    
    print(f"After excluding total/subtotal rows: {len(df):,} rows remaining")
    
    # Now filter to only rows with valid numeric reserve numbers
    df['reserve_numeric'] = pd.to_numeric(df[reserve_num_col], errors='coerce')
    df = df[df['reserve_numeric'].notna()].copy()
    
    # Also exclude rows where Total is abnormally large (likely missed subtotals)
    df['total_numeric'] = pd.to_numeric(df[total_col], errors='coerce')
    df = df[df['total_numeric'].notna()].copy()
    
    # Exclude obvious outliers (normal charter max is around $10K-20K)
    df = df[df['total_numeric'] < 100000].copy()
    
    print(f"After additional filtering: {len(df):,} data rows")
    
    print(f"Excel file summary:")
    print(f"  Total data rows: {len(df):,}")
    if len(df) > 0:
        # Parse dates properly
        df[reserve_date_col] = pd.to_datetime(df[reserve_date_col], errors='coerce')
        print(f"  Date range: {df[reserve_date_col].min()} to {df[reserve_date_col].max()}")
        print(f"  Reserve number range: {int(df['reserve_numeric'].min())} to {int(df['reserve_numeric'].max())}")
    
    # Use the already filtered data
    df_valid = df.copy()
    df_valid['reserve_clean'] = df_valid['reserve_numeric'].astype('Int64')
    
    # Calculate totals from Excel (using already filtered data)
    excel_total = df_valid['total_numeric'].sum()
    excel_count = len(df_valid)
    
    print(f"\nExcel totals:")
    print(f"  Total charges: ${excel_total:,.2f}")
    print(f"  Number of records: {excel_count:,}")
    print(f"  Average charge: ${excel_total/excel_count:,.2f}")
    
    # Get database data
    conn = get_db_connection()
    cur = conn.cursor()
    
    print(f"\n{'=' * 100}")
    print("DATABASE COMPARISON")
    print('=' * 100)
    
    # Get all charters with reserve numbers
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            COUNT(reserve_number) as with_reserve,
            SUM(COALESCE(total_amount_due, rate, 0)) as total_charges
        FROM charters
        WHERE reserve_number IS NOT NULL
    """)
    
    db_row = cur.fetchone()
    
    print(f"\nDatabase charters:")
    print(f"  Total charters with reserve #: {db_row[1]:,}")
    print(f"  Total charges: ${db_row[2]:,.2f}")
    
    # Compare by reserve number - sample matching
    print(f"\n{'=' * 100}")
    print("RESERVE NUMBER MATCHING")
    print('=' * 100)
    
    # Get sample reserve numbers from Excel
    excel_reserves = set(df_valid['reserve_clean'].astype(int).unique())
    print(f"\nUnique reserve numbers in Excel: {len(excel_reserves):,}")
    
    # Get reserve numbers from database
    cur.execute("SELECT DISTINCT reserve_number FROM charters WHERE reserve_number IS NOT NULL")
    db_reserves = set()
    for r in cur.fetchall():
        if r[0]:
            try:
                db_reserves.add(int(r[0]))
            except (ValueError, TypeError):
                # Skip non-numeric reserve numbers like 'AUDIT002004'
                pass
    print(f"Unique reserve numbers in database: {len(db_reserves):,}")
    
    # Find matches and differences
    in_both = excel_reserves & db_reserves
    only_excel = excel_reserves - db_reserves
    only_db = db_reserves - excel_reserves
    
    print(f"\nIn both Excel and database: {len(in_both):,}")
    print(f"Only in Excel: {len(only_excel):,}")
    print(f"Only in database: {len(only_db):,}")
    
    if len(only_excel) > 0:
        print(f"\nSample reserves only in Excel (first 10): {sorted(only_excel)[:10]}")
    
    if len(only_db) > 0:
        print(f"Sample reserves only in database (first 10): {sorted(only_db)[:10]}")
    
    # Detailed comparison for matching reserves
    print(f"\n{'=' * 100}")
    print("AMOUNT COMPARISON FOR MATCHING RESERVES")
    print('=' * 100)
    
    # Get 20 random matching reserves
    sample_reserves = sorted(list(in_both))[:20]
    
    print(f"\n{'Reserve':<10} {'Excel Date':<12} {'Excel Total':>15} {'DB Date':<12} {'DB Total':>15} {'Difference':>15}")
    print('-' * 100)
    
    for reserve_num in sample_reserves:
        # Excel data
        excel_row = df_valid[df_valid['reserve_clean'] == reserve_num].iloc[0]
        excel_date = excel_row[reserve_date_col]
        excel_amt = float(excel_row[total_col]) if pd.notna(excel_row[total_col]) else 0.0
        
        # Database data
        cur.execute("""
            SELECT charter_date, 
                   COALESCE(total_amount_due, rate, 0) as charge
            FROM charters 
            WHERE reserve_number = %s
            LIMIT 1
        """, (str(reserve_num),))
        
        db_row = cur.fetchone()
        if db_row:
            db_date = db_row[0]
            db_amt = float(db_row[1]) if db_row[1] else 0.0
            diff = excel_amt - db_amt
            
            excel_date_str = excel_date.strftime('%Y-%m-%d') if pd.notna(excel_date) else 'N/A'
            db_date_str = str(db_date) if db_date else 'N/A'
            
            print(f"{reserve_num:<10} {excel_date_str:<12} ${excel_amt:>13,.2f} {db_date_str:<12} ${db_amt:>13,.2f} ${diff:>13,.2f}")
    
    # Summary of discrepancies
    print(f"\n{'=' * 100}")
    print("DISCREPANCY ANALYSIS")
    print('=' * 100)
    
    total_excel_matched = 0
    total_db_matched = 0
    count_matched = 0
    
    for reserve_num in in_both:
        # Excel
        excel_rows = df_valid[df_valid['reserve_clean'] == reserve_num]
        if len(excel_rows) > 0:
            excel_amt = pd.to_numeric(excel_rows[total_col], errors='coerce').sum()
            total_excel_matched += excel_amt
        
        # Database
        cur.execute("""
            SELECT SUM(COALESCE(total_amount_due, rate, 0))
            FROM charters 
            WHERE reserve_number = %s
        """, (str(reserve_num),))
        
        db_amt = cur.fetchone()[0] or 0
        total_db_matched += db_amt
        count_matched += 1
    
    print(f"\nFor {count_matched:,} matching reserve numbers:")
    print(f"  Excel total: ${total_excel_matched:,.2f}")
    print(f"  Database total: ${total_db_matched:,.2f}")
    print(f"  Difference: ${total_excel_matched - total_db_matched:,.2f}")
    print(f"  Database is {100 * total_db_matched / total_excel_matched:.1f}% of Excel" if total_excel_matched > 0 else "")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
