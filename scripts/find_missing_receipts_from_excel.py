"""Find which receipts are missing from the Excel export."""
import pandas as pd
import psycopg2

file = r'L:\limo\reports\receipts_reconciliation_20251219_123858.xlsx'

# Get all receipt IDs from database
conn = psycopg2.connect(
    host='localhost', 
    dbname='almsdata', 
    user='postgres', 
    password='***REDACTED***'
)

cur = conn.cursor()
cur.execute('SELECT receipt_id, receipt_date, vendor_name, gross_amount FROM receipts ORDER BY receipt_id')
db_receipts = pd.DataFrame(cur.fetchall(), columns=['receipt_id', 'receipt_date', 'vendor_name', 'gross_amount'])
cur.close()
conn.close()

# Get all receipt IDs from Excel
xl = pd.ExcelFile(file)
excel_receipts = pd.read_excel(xl, 'Receipts')

print(f'Database: {len(db_receipts):,} receipts')
print(f'Excel: {len(excel_receipts):,} receipts')

# Find missing
db_ids = set(db_receipts['receipt_id'])
excel_ids = set(excel_receipts['receipt_id'])

missing_ids = db_ids - excel_ids
extra_ids = excel_ids - db_ids

if missing_ids:
    print(f'\n❌ {len(missing_ids)} receipts MISSING from Excel:')
    missing_df = db_receipts[db_receipts['receipt_id'].isin(missing_ids)].sort_values('receipt_id')
    for _, row in missing_df.iterrows():
        print(f'  ID {row["receipt_id"]}: {row["receipt_date"]} - {row["vendor_name"]} - ${row["gross_amount"]:.2f}')

if extra_ids:
    print(f'\n⚠️ {len(extra_ids)} receipts in Excel but NOT in database:')
    extra_df = excel_receipts[excel_receipts['receipt_id'].isin(extra_ids)].sort_values('receipt_id')
    for _, row in extra_df.head(10).iterrows():
        print(f'  ID {row["receipt_id"]}: {row["receipt_date"]} - {row["vendor_name"]} - ${row["gross_amount"]:.2f}')

if not missing_ids and not extra_ids:
    print('\n✅ All receipts match perfectly!')
