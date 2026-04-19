"""
Audit LMS payments for 2015-2026 reserves against charter_payments
"""
import pyodbc
import pandas as pd
import psycopg2
from datetime import datetime

# LMS connection
lms_file = r'L:\lms2026b.mdb'
conn_str = f'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={lms_file};'

try:
    lms_conn = pyodbc.connect(conn_str)
    
    # Query LMS Payment table for all reserves
    query = """
    SELECT 
      Reserve_No,
      COUNT(*) AS lms_payment_count,
      SUM(Amount) AS lms_total_amount,
      MIN(LastUpdated) AS earliest_date,
      MAX(LastUpdated) AS latest_date
    FROM Payment
    WHERE Reserve_No IS NOT NULL AND Reserve_No <> ''
    GROUP BY Reserve_No
    ORDER BY Reserve_No
    """
    
    df_lms = pd.read_sql(query, lms_conn)
    print("=" * 80)
    print("LMS PAYMENT DATA (2015-2026 scope)")
    print("=" * 80)
    print(f"Total reserves with payments in LMS: {len(df_lms):,}")
    print(f"Total LMS payment rows: {df_lms['lms_payment_count'].sum():,}")
    print(f"Total LMS amount: ${df_lms['lms_total_amount'].sum():,.2f}")
    print()
    
    lms_conn.close()
    
    # Now query ALMS to compare
    alms_conn = psycopg2.connect(
        host='localhost', port=5432, database='almsdata',
        user='postgres', password='ArrowLimousine'
    )
    
    alms_cursor = alms_conn.cursor()
    
    # Get current charter_payments coverage by reserve
    alms_cursor.execute("""
    SELECT 
      cp.charter_id AS reserve_no,
      COUNT(*) AS cp_payment_count,
      ROUND(SUM(cp.amount)::numeric, 2) AS cp_total_amount,
      MIN(cp.payment_date) AS earliest_date,
      MAX(cp.payment_date) AS latest_date
    FROM charter_payments cp
    WHERE cp.charter_id IS NOT NULL
    GROUP BY cp.charter_id
    ORDER BY cp.charter_id
    """)
    
    df_alms = pd.DataFrame(alms_cursor.fetchall(), 
                           columns=['reserve_no', 'cp_payment_count', 'cp_total_amount', 
                                   'earliest_date', 'latest_date'])
    
    # Convert Decimal to float for pandas arithmetic
    df_alms['cp_total_amount'] = df_alms['cp_total_amount'].astype(float)
    df_lms['lms_total_amount'] = df_lms['lms_total_amount'].astype(float)
    
    print("=" * 80)
    print("ALMS CHARTER_PAYMENTS DATA")
    print("=" * 80)
    print(f"Total reserves with payments in ALMS: {len(df_alms):,}")
    print(f"Total ALMS payment rows: {df_alms['cp_payment_count'].sum():,}")
    print(f"Total ALMS amount: ${df_alms['cp_total_amount'].sum():,.2f}")
    print()
    
    # Merge and find mismatches
    df_merged = pd.merge(
        df_lms.rename(columns={'Reserve_No': 'reserve_no'}),
        df_alms,
        on='reserve_no',
        how='outer',
        indicator=True
    )
    
    # Find mismatches (amount difference > $0.01)
    df_merged['amount_diff'] = df_merged['lms_total_amount'].fillna(0) - df_merged['cp_total_amount'].fillna(0)
    df_merged['count_diff'] = df_merged['lms_payment_count'].fillna(0).astype(int) - df_merged['cp_payment_count'].fillna(0).astype(int)
    
    df_mismatches = df_merged[
        (df_merged['amount_diff'].abs() > 0.01) | 
        (df_merged['count_diff'] != 0) |
        (df_merged['_merge'] != 'both')
    ].copy()
    
    print("=" * 80)
    print("MISMATCHES (LMS vs ALMS charter_payments)")
    print("=" * 80)
    print(f"Total mismatches: {len(df_mismatches):,}")
    print()
    
    # Show breakdown
    in_lms_only = df_mismatches[df_mismatches['_merge'] == 'left_only']
    in_alms_only = df_mismatches[df_mismatches['_merge'] == 'right_only']
    amount_diff = df_mismatches[(df_mismatches['_merge'] == 'both') & (df_mismatches['amount_diff'].abs() > 0.01)]
    
    print(f"  In LMS only (no ALMS record): {len(in_lms_only):,}")
    if len(in_lms_only) > 0:
        print(f"    Total LMS amount missing: ${in_lms_only['lms_total_amount'].sum():,.2f}")
    print()
    
    print(f"  In ALMS only (no LMS record): {len(in_alms_only):,}")
    if len(in_alms_only) > 0:
        print(f"    Total ALMS amount extra: ${in_alms_only['cp_total_amount'].sum():,.2f}")
    print()
    
    print(f"  Amount mismatch (both exist but differ): {len(amount_diff):,}")
    if len(amount_diff) > 0:
        print(f"    Total LMS: ${amount_diff['lms_total_amount'].sum():,.2f}")
        print(f"    Total ALMS: ${amount_diff['cp_total_amount'].sum():,.2f}")
        print(f"    Difference: ${amount_diff['amount_diff'].sum():,.2f}")
    print()
    
    # Show top 20 mismatches
    print("=" * 80)
    print("TOP 20 MISMATCHES (by $ amount)")
    print("=" * 80)
    df_mismatches['abs_diff'] = df_mismatches['amount_diff'].abs()
    df_show = df_mismatches.nlargest(20, 'abs_diff')[
        ['reserve_no', 'lms_payment_count', 'cp_payment_count', 'lms_total_amount', 'cp_total_amount', 'amount_diff']
    ]
    for idx, row in df_show.iterrows():
        lms_cnt = int(row['lms_payment_count']) if pd.notna(row['lms_payment_count']) else 0
        alms_cnt = int(row['cp_payment_count']) if pd.notna(row['cp_payment_count']) else 0
        lms_amt = float(row['lms_total_amount']) if pd.notna(row['lms_total_amount']) else 0
        alms_amt = float(row['cp_total_amount']) if pd.notna(row['cp_total_amount']) else 0
        diff = float(row['amount_diff']) if pd.notna(row['amount_diff']) else 0
        print(f"{row['reserve_no']:>8}  LMS:{lms_cnt:>3}/${lms_amt:>10,.2f}  ALMS:{alms_cnt:>3}/${alms_amt:>10,.2f}  DIFF:{diff:>12,.2f}")
    
    alms_conn.close()
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
