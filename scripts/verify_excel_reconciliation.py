"""Verify Excel reconciliation file against database."""
import pandas as pd
import psycopg2
import sys

file = r'L:\limo\reports\receipts_reconciliation_20251219_123858.xlsx'

try:
    xl = pd.ExcelFile(file)
    receipts = pd.read_excel(xl, 'Receipts')
    unmatched = pd.read_excel(xl, 'Unmatched')
    duplicates = pd.read_excel(xl, 'Duplicates')
    
    conn = psycopg2.connect(
        host='localhost', 
        dbname='almsdata', 
        user='postgres', 
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    # Database counts
    cur.execute('SELECT COUNT(*) FROM receipts')
    db_count = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM receipts WHERE banking_transaction_id IS NULL')
    db_unmatched = cur.fetchone()[0]
    
    print('='*70)
    print('EXCEL RECONCILIATION FILE VERIFICATION')
    print('='*70)
    
    print('\nRecord Counts:')
    print(f'  Database total receipts: {db_count:,}')
    print(f'  Excel total receipts: {len(receipts):,}')
    print(f'  Match: {"✅" if len(receipts) == db_count else "❌ MISMATCH - Missing " + str(db_count - len(receipts)) + " records"}')
    
    print(f'\n  Database unmatched: {db_unmatched:,}')
    print(f'  Excel unmatched: {len(unmatched):,}')
    print(f'  Match: {"✅" if len(unmatched) == db_unmatched else "❌ MISMATCH"}')
    
    print(f'\nExcel Structure:')
    print(f'  Sheets: {xl.sheet_names}')
    print(f'  Receipts columns: {len(receipts.columns)}')
    print(f'  Column names: {list(receipts.columns[:20])}...')
    
    # Critical columns check
    critical = ['receipt_id', 'receipt_date', 'vendor_name', 'gross_amount', 
                'banking_transaction_id', 'match_status']
    missing = [c for c in critical if c not in receipts.columns]
    print(f'\n  Critical columns missing: {missing if missing else "None ✅"}')
    
    # Data quality
    print(f'\nData Quality:')
    print(f'  Null receipt_id: {receipts["receipt_id"].isna().sum()}')
    print(f'  Null vendor_name: {receipts["vendor_name"].isna().sum()}')
    print(f'  Null gross_amount: {receipts["gross_amount"].isna().sum()}')
    print(f'  Null receipt_date: {receipts["receipt_date"].isna().sum()}')
    
    # Unmatched breakdown
    print(f'\nUnmatched Receipts by Year:')
    unmatched['receipt_date'] = pd.to_datetime(unmatched['receipt_date'])
    year_breakdown = unmatched.groupby(unmatched['receipt_date'].dt.year).agg({
        'receipt_id': 'count',
        'gross_amount': 'sum'
    }).round(2)
    
    for year, row in year_breakdown.iterrows():
        print(f'  {int(year)}: {int(row["receipt_id"]):,} receipts, ${row["gross_amount"]:,.2f}')
    
    # Duplicates analysis
    if len(duplicates) > 0:
        print(f'\nDuplicate Analysis:')
        print(f'  Total flagged duplicates: {len(duplicates):,}')
        duplicates['receipt_date'] = pd.to_datetime(duplicates['receipt_date'])
        dup_by_year = duplicates.groupby(duplicates['receipt_date'].dt.year).size()
        for year, count in dup_by_year.items():
            print(f'    {int(year)}: {count:,}')
    
    # Color coding verification
    if 'match_status' in receipts.columns:
        print(f'\nMatch Status Distribution:')
        status_counts = receipts['match_status'].value_counts()
        for status, count in status_counts.items():
            print(f'  {status}: {count:,}')
    
    cur.close()
    conn.close()
    
    print('\n' + '='*70)
    if len(receipts) == db_count:
        print('✅ VERIFICATION PASSED - All database receipts are in Excel')
    else:
        print('❌ VERIFICATION FAILED - Record count mismatch')
        print(f'   Missing {db_count - len(receipts):,} receipts from Excel export')
    print('='*70)
    
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
