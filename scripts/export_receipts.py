"""Export receipts to Excel"""
import psycopg2, pandas as pd, os
import warnings
warnings.filterwarnings('ignore')

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)

print('Exporting receipts...')
df = pd.read_sql('SELECT * FROM receipts ORDER BY receipt_date DESC, receipt_id', conn)

# Convert ALL columns to check types
for col in df.columns:
    # Check if it's a datetime type
    if isinstance(df[col].dtype, pd.DatetimeTZDtype):
        df[col] = df[col].dt.tz_convert(None)
    elif pd.api.types.is_datetime64_any_dtype(df[col]):
        # Already timezone-naive, but ensure it
        pass

# Save to CSV first as workaround
print('Saving as CSV first...')
df.to_csv('L:\\limo\\reports\\receipts_complete_export.csv', index=False)

# Then read and save as Excel
print('Converting to Excel...')
df2 = pd.read_csv('L:\\limo\\reports\\receipts_complete_export.csv')
df2.to_excel('L:\\limo\\reports\\receipts_complete_export.xlsx', index=False, engine='openpyxl')
print(f'✅ Exported {len(df):,} receipts')
print(f'   Date range: {df["receipt_date"].min()} to {df["receipt_date"].max()}')
print(f'   Total: ${df["gross_amount"].sum():,.2f}')
conn.close()
