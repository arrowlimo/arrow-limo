#!/usr/bin/env python3
"""Find remaining 22 missing Scotia transactions from your updated file."""

import pandas as pd
import psycopg2

# Load the updated Scotia file
df_file = pd.read_excel(r"L:\limo\data\2012_scotia_transactions_for_editing.xlsx")

print("=" * 100)
print("SCOTIA FILE ANALYSIS - AFTER AUTO-ENTRY DATE FIXES")
print("=" * 100)

print(f"\nTotal rows in file: {len(df_file)}")
print(f"Columns: {list(df_file.columns)}")

# Check dates
df_file['year'] = pd.to_datetime(df_file['date'], errors='coerce').dt.year
year_counts = df_file['year'].value_counts().sort_index()
print(f"\nRows by year:")
for year, count in year_counts.items():
    if pd.notna(year):
        print(f"  {int(year)}: {count}")
    else:
        print(f"  (missing date): {count}")

df_2012 = df_file[df_file['year'] == 2012]
print(f"\nTotal 2012 rows: {len(df_2012)}")
print(f"Date range: {df_2012['date'].min()} to {df_2012['date'].max()}")

# Now compare to database
DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

cur.execute("""
    SELECT COUNT(*) FROM banking_transactions
    WHERE account_number = '903990106011'
      AND EXTRACT(YEAR FROM transaction_date) = 2012
""")
db_count = cur.fetchone()[0]

print(f"\nDatabase Scotia 2012 transactions: {db_count}")
print(f"File 2012 transactions: {len(df_2012)}")
print(f"Difference (to import): {len(df_2012) - db_count}")

# Find which ones are missing
df_2012['date_normalized'] = pd.to_datetime(df_2012['date']).dt.date
df_2012['debit'] = pd.to_numeric(df_2012['debit/withdrawal'], errors='coerce').fillna(0).round(2)
df_2012['credit'] = pd.to_numeric(df_2012['deposit/credit'], errors='coerce').fillna(0).round(2)
df_2012['balance'] = pd.to_numeric(df_2012['balance'], errors='coerce').fillna(0).round(2)

# Get from database
cur.execute("""
    SELECT transaction_date::date, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
      AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date
""")
db_rows = cur.fetchall()

df_db = pd.DataFrame(db_rows, columns=['date', 'debit', 'credit', 'balance'])
df_db['debit'] = pd.to_numeric(df_db['debit'], errors='coerce').fillna(0).round(2)
df_db['credit'] = pd.to_numeric(df_db['credit'], errors='coerce').fillna(0).round(2)
df_db['balance'] = pd.to_numeric(df_db['balance'], errors='coerce').fillna(0).round(2)

# Create hashes for matching
df_2012['hash'] = df_2012.apply(lambda x: f"{x['date_normalized']}|{x['debit']}|{x['credit']}|{x['balance']}", axis=1)
df_db['hash'] = df_db.apply(lambda x: f"{x['date']}|{x['debit']}|{x['credit']}|{x['balance']}", axis=1)

file_hashes = set(df_2012['hash'])
db_hashes = set(df_db['hash'])
missing = file_hashes - db_hashes

print(f"\n" + "=" * 100)
print(f"MISSING {len(missing)} TRANSACTIONS")
print("=" * 100)

missing_df = df_2012[df_2012['hash'].isin(missing)].sort_values('date')
for idx, row in missing_df.iterrows():
    print(f"\n  {row['date_normalized']} | {row['Description'][:40]:40s}")
    print(f"    Debit: ${row['debit']:>9.2f} | Credit: ${row['credit']:>9.2f} | Balance: ${row['balance']:>10.2f}")

# Export for import
output_path = r"L:\limo\data\scotia_22_missing_transactions.xlsx"
missing_df[['date', 'Description', 'debit/withdrawal', 'deposit/credit', 'balance']].to_excel(output_path, index=False)
print(f"\n✓ Exported to: {output_path}")

cur.close()
conn.close()
