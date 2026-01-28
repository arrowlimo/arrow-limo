"""Update banking_accounts_all_years.xlsx with corrected data from all bank accounts."""

import pandas as pd
import psycopg2
from openpyxl import load_workbook

print("="*80)
print("UPDATING BANKING ACCOUNTS EXCEL FILE")
print("="*80)
print()

# Database connection
conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REMOVED***",
    host="localhost"
)

# File paths
input_file = r"L:\limo\reports\banking_accounts_all_years.xlsx"
output_file = r"L:\limo\reports\banking_accounts_all_years.xlsx"
backup_file = r"L:\limo\reports\banking_accounts_all_years_backup.xlsx"

# Read existing file
print("Reading existing Excel file...")
excel_data = pd.read_excel(input_file, sheet_name=None)
print(f"Found {len(excel_data)} sheets: {list(excel_data.keys())}")
print()

# Check if 1010 exists
if '1010' in excel_data:
    print("⚠️  Found account 1010 (BOGUS SCOTIA DATA)")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE account_number = '1010'")
    count = cur.fetchone()[0]
    print(f"   Database has {count} transactions for account 1010")
    print("   → This account will be REMOVED from Excel")
    print()
    cur.close()

# Get all account numbers from database
print("Fetching all banking accounts from database...")
cur = conn.cursor()
cur.execute("""
    SELECT DISTINCT account_number, COUNT(*) as count
    FROM banking_transactions
    WHERE account_number IS NOT NULL
    AND account_number != '1010'
    GROUP BY account_number
    ORDER BY account_number
""")
accounts = cur.fetchall()
print(f"Found {len(accounts)} accounts:")
for acc, count in accounts:
    print(f"  {acc}: {count:,} transactions")
print()

# Query all account data
account_dataframes = {}
for account_number, _ in accounts:
    print(f"Fetching data for account {account_number}...")
    cur.execute("""
        SELECT 
            transaction_id,
            account_number,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            balance,
            category,
            vendor_extracted as vendor_name,
            created_at,
            updated_at
        FROM banking_transactions
        WHERE account_number = %s
        ORDER BY transaction_date, transaction_id
    """, (account_number,))
    
    rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=[
        'transaction_id', 'account_number', 'transaction_date', 'description',
        'debit_amount', 'credit_amount', 'balance', 'category', 'vendor_name',
        'created_at', 'updated_at'
    ])
    account_dataframes[account_number] = df
    print(f"  → {len(rows):,} transactions")

print()

# Backup original file
print(f"Creating backup: {backup_file}")
import shutil
shutil.copy2(input_file, backup_file)
print("✓ Backup created")
print()

# Update sheets
print("Updating Excel file...")
with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    for sheet_name, df in excel_data.items():
        if sheet_name == '1010':
            print(f"  ✗ SKIPPING sheet '{sheet_name}' (bogus Scotia data)")
            continue
        elif sheet_name in account_dataframes:
            new_df = account_dataframes[sheet_name]
            print(f"  ✓ UPDATING sheet '{sheet_name}' with {len(new_df):,} rows (corrected data from database)")
            new_df.to_excel(writer, sheet_name=sheet_name, index=False)
        else:
            print(f"  → Keeping sheet '{sheet_name}' ({len(df):,} rows)")
            df.to_excel(writer, sheet_name=sheet_name, index=False)

print()
print("="*80)
print("SUMMARY")
print("="*80)
print()
for account_number, df in account_dataframes.items():
    print(f"✓ Updated sheet {account_number} with {len(df):,} transactions")
print(f"✗ Removed bogus account 1010")
print(f"✓ Backup saved to: {backup_file}")
print(f"✓ Updated file: {output_file}")
print()

# Verify database - check if 1010 should be deleted from database too
cur.execute("""
    SELECT 
        COUNT(*) as txn_count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        SUM(debit_amount) as total_debits,
        COUNT(DISTINCT description) as unique_descriptions
    FROM banking_transactions
    WHERE account_number = '1010'
""")

if cur.fetchone()[0] > 0:
    print("="*80)
    print("⚠️  DATABASE CLEANUP NEEDED")
    print("="*80)
    print()
    cur.execute("""
        SELECT 
            COUNT(*) as txn_count,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date,
            SUM(debit_amount) as total_debits,
            COUNT(DISTINCT description) as unique_descriptions
        FROM banking_transactions
        WHERE account_number = '1010'
    """)
    count, first, last, debits, desc_count = cur.fetchone()
    print(f"Account 1010 in database has:")
    print(f"  Transactions: {count:,}")
    print(f"  Date Range: {first} to {last}")
    print(f"  Total Debits: ${float(debits):,.2f}")
    print(f"  Unique Descriptions: {desc_count}")
    print()
    print("RECOMMENDATION:")
    print("  This appears to be duplicate/bogus Scotia data from an incorrect import.")
    print("  Consider running: DELETE FROM banking_transactions WHERE account_number = '1010';")
    print()

cur.close()
conn.close()
