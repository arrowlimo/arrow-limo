"""
Analyze comprehensive LMS charge summary files (2007-2026)
Files: 07_12chargesummary.xls and 13_26chargesummary.xls
These contain complete charge breakdowns from printed LMS reports
"""
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def parse_07_12_file():
    """Parse 2007-2012 charge summary - NO HEADER, starts with data"""
    file_path = r'L:\limo\docs\07_12chargesummary.xls'
    
    print("=" * 100)
    print("FILE: 07_12chargesummary.xls (2007-2012)")
    print("=" * 100)
    
    # Read without header - data starts at row 0
    df = pd.read_excel(file_path, sheet_name='Sheet1', header=None)
    
    # Based on pattern: Date, nan, Reserve#, nan, ServiceFee, nan, charges...
    # Column pattern repeats: value, nan, value, nan...
    # Extract non-nan columns
    data_cols = []
    for i in range(0, len(df.columns), 2):
        if i < len(df.columns):
            data_cols.append(i)
    
    df_clean = df[data_cols].copy()
    
    # Assign column names based on position
    # Inspecting the pattern, looks like:
    # Col 0: Date, Col 2: Reserve#, Col 4: Service Fee, then various charges, last col: Total
    col_names = ['date', 'reserve_number', 'service_fee']
    
    # Need to inspect one row to see all charge columns
    print(f"\nTotal columns (including nan): {len(df.columns)}")
    print(f"Data columns (excluding nan): {len(df_clean.columns)}")
    print(f"\nFirst row values:")
    first_row = df.iloc[0]
    for i, val in enumerate(first_row):
        if pd.notna(val):
            print(f"  Col {i}: {val}")
    
    # For now, just extract date, reserve, and total
    df_clean.columns = range(len(df_clean.columns))
    df_clean = df_clean.rename(columns={
        0: 'date',
        1: 'reserve_number',
        len(df_clean.columns) - 1: 'total'
    })
    
    # Clean data
    df_clean['date'] = pd.to_datetime(df_clean['date'], errors='coerce')
    df_clean['reserve_number'] = pd.to_numeric(df_clean['reserve_number'], errors='coerce').astype('Int64')
    df_clean['total'] = pd.to_numeric(df_clean['total'], errors='coerce')
    
    # Remove invalid rows
    df_clean = df_clean[df_clean['date'].notna() & df_clean['reserve_number'].notna()]
    
    print(f"\nValid records: {len(df_clean):,}")
    print(f"Date range: {df_clean['date'].min()} to {df_clean['date'].max()}")
    print(f"Total amount: ${df_clean['total'].sum():,.2f}")
    
    # Year breakdown
    df_clean['year'] = df_clean['date'].dt.year
    year_summary = df_clean.groupby('year').agg({
        'reserve_number': 'count',
        'total': 'sum'
    })
    
    print(f"\nYear breakdown:")
    for year, row in year_summary.iterrows():
        print(f"  {int(year)}: {int(row['reserve_number']):,} records, ${row['total']:,.2f}")
    
    return df_clean

def parse_13_26_file():
    """Parse 2013-2026 charge summary - header at row 11"""
    file_path = r'L:\limo\docs\13_26chargesummary.xls'
    
    print("\n" + "=" * 100)
    print("FILE: 13_26chargesummary.xls (2013-2026)")
    print("=" * 100)
    
    # Header is at row 11, data starts at row 14
    df = pd.read_excel(file_path, sheet_name='Sheet1', header=11, skiprows=[12, 13])
    
    # Clean column names
    df.columns = [str(col).strip().replace('\n', ' ').replace('  ', ' ') if pd.notna(col) else f'Unnamed_{i}' 
                  for i, col in enumerate(df.columns)]
    
    print(f"\nColumns: {list(df.columns)}")
    
    # Find reserve number and date columns
    reserve_col = None
    date_col = None
    total_col = None
    
    for col in df.columns:
        if 'reserve' in col.lower() and 'number' in col.lower():
            reserve_col = col
        elif 'date' in col.lower():
            date_col = col
        elif col == 'Total':
            total_col = col
    
    print(f"\nKey columns found:")
    print(f"  Date: {date_col}")
    print(f"  Reserve: {reserve_col}")
    print(f"  Total: {total_col}")
    
    # Clean data
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    if reserve_col:
        # Handle string reserve numbers like '017975'
        df[reserve_col] = df[reserve_col].astype(str).str.strip()
        df[reserve_col] = pd.to_numeric(df[reserve_col], errors='coerce').astype('Int64')
    if total_col:
        df[total_col] = pd.to_numeric(df[total_col], errors='coerce')
    
    # Remove invalid rows
    df = df[df[date_col].notna() & df[reserve_col].notna()]
    
    print(f"\nValid records: {len(df):,}")
    print(f"Date range: {df[date_col].min()} to {df[date_col].max()}")
    if total_col:
        print(f"Total amount: ${df[total_col].sum():,.2f}")
    
    # Year breakdown
    df['year'] = df[date_col].dt.year
    year_summary = df.groupby('year').agg({
        reserve_col: 'count',
        total_col: 'sum' if total_col else 'count'
    })
    
    print(f"\nYear breakdown:")
    for year, row in year_summary.iterrows():
        if total_col:
            print(f"  {int(year)}: {int(row[reserve_col]):,} records, ${row[total_col]:,.2f}")
        else:
            print(f"  {int(year)}: {int(row[reserve_col]):,} records")
    
    # Show charge column breakdown
    charge_cols = []
    for col in df.columns:
        if col not in [date_col, reserve_col, total_col, 'year']:
            if pd.api.types.is_numeric_dtype(df[col]):
                col_sum = df[col].sum()
                if abs(col_sum) > 0.01:
                    charge_cols.append((col, col_sum))
    
    if charge_cols:
        charge_cols.sort(key=lambda x: x[1], reverse=True)
        print(f"\nCharge types (top 10):")
        for col, total in charge_cols[:10]:
            print(f"  {col}: ${total:,.2f}")
    
    return df

def compare_with_database():
    """Compare files with PostgreSQL database"""
    print("\n" + "=" * 100)
    print("DATABASE COMPARISON")
    print("=" * 100)
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get database totals by year
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM c.charter_date) as year,
            COUNT(DISTINCT c.charter_id) as charter_count,
            SUM(c.total_amount_due) as total_amount_due,
            SUM(COALESCE(cc.amount, 0)) as sum_charges
        FROM charters c
        LEFT JOIN charter_charges cc ON c.charter_id = cc.charter_id
        WHERE EXTRACT(YEAR FROM c.charter_date) BETWEEN 2007 AND 2026
        GROUP BY EXTRACT(YEAR FROM c.charter_date)
        ORDER BY year
    """)
    
    db_data = cur.fetchall()
    
    print(f"\nPostgreSQL totals by year:")
    for row in db_data:
        print(f"  {int(row['year'])}: {row['charter_count']:,} charters, "
              f"total_due=${float(row['total_amount_due']):,.2f}, "
              f"charges=${float(row['sum_charges']):,.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    df_07_12 = parse_07_12_file()
    df_13_26 = parse_13_26_file()
    compare_with_database()
    
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"\n07-12 file: {len(df_07_12):,} records, ${df_07_12['total'].sum():,.2f}")
    print(f"13-26 file: {len(df_13_26):,} records")
    print(f"\nThese are the authoritative LMS charge records.")
    print(f"Next: Import detailed charge breakdowns into charter_charges table.")
