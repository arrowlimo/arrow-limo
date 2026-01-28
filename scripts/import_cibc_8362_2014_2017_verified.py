"""
Import CIBC 0228362 (8362) verified banking data 2014-2017
Account: 0228362 (CIBC checking account - PRIMARY)
mapped_bank_account_id = 1

VERIFIED FILE: L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\2014-2017 CIBC 8362.xlsx
"""
import pandas as pd
import psycopg2
from datetime import datetime
import hashlib
import os
import sys

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

file_path = r"L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\2014-2017 CIBC 8362.xlsx"

print("=" * 80)
print("CIBC Account 0228362 (8362) - 2014-2017 VERIFIED IMPORT")
print("mapped_bank_account_id = 1 (PRIMARY ACCOUNT)")
print("=" * 80)

# Load Excel file
print(f"\n📁 Loading: {file_path}")
df = pd.read_excel(file_path)
print(f"✅ Loaded {len(df):,} rows")

# Fix the typo: "214" → "2014"
print("\n🔧 Fixing date typo (214 → 2014)...")
df['date'] = df['date'].astype(str).str.replace('/214', '/2014', regex=False)
df['date'] = pd.to_datetime(df['date'], errors='coerce')

# Check for invalid dates
nat_count = df['date'].isna().sum()
if nat_count > 0:
    print(f"⚠️ Warning: {nat_count} invalid dates found")
    bad_rows = df[df['date'].isna()]
    print(bad_rows[['date', 'Description']].head())
    sys.exit(1)

print(f"✅ Date range: {df['date'].min()} to {df['date'].max()}")

# Clean and standardize columns
df['debit'] = pd.to_numeric(df['debit/withdrawal'], errors='coerce').fillna(0)
df['credit'] = pd.to_numeric(df['deposit/credit'], errors='coerce').fillna(0)
df['balance'] = pd.to_numeric(df['balance'], errors='coerce')
df['description'] = df['Description'].fillna('').astype(str).str.strip()

# Calculate amount (credits are positive, debits are negative)
df['amount'] = df['credit'] - df['debit']

print(f"\n💰 Transaction Summary:")
print(f"   Debits:  {df[df['debit'] > 0]['debit'].count():,} transactions, ${df['debit'].sum():,.2f}")
print(f"   Credits: {df[df['credit'] > 0]['credit'].count():,} transactions, ${df['credit'].sum():,.2f}")
print(f"   Net:     ${df['amount'].sum():,.2f}")

# Connect to database
print("\n🔌 Connecting to database...")
conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Check existing data
cur.execute("""
    SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date)
    FROM banking_transactions
    WHERE bank_id = 1
    AND transaction_date BETWEEN '2014-01-01' AND '2017-12-31'
""")
existing_count, existing_min, existing_max = cur.fetchone()
print(f"📊 Existing banking_transactions (2014-2017, bank_id=1): {existing_count:,}")
if existing_count > 0:
    print(f"   Range: {existing_min} to {existing_max}")

# Prepare import
print("\n🚀 Starting import...")
imported = 0
duplicates = 0
errors = 0

for idx, row in df.iterrows():
    try:
        trans_date = row['date'].date()
        description = row['description']
        amount = float(row['amount'])
        balance = float(row['balance']) if pd.notna(row['balance']) else None
        
        # Create deterministic hash for deduplication
        hash_input = f"{trans_date}|{description}|{amount:.2f}|CIBC8362"
        trans_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
        
        # Insert with deduplication
        cur.execute("""
            INSERT INTO banking_transactions (
                bank_id,
                account_number,
                transaction_date,
                description,
                credit_amount,
                debit_amount,
                balance,
                transaction_hash,
                source_file,
                created_at
            )
            SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            WHERE NOT EXISTS (
                SELECT 1 FROM banking_transactions
                WHERE transaction_hash = %s
            )
        """, (
            1,  # bank_id = 1 (CIBC 0228362)
            '0228362',  # account_number
            trans_date,
            description,
            float(row['credit']) if row['credit'] > 0 else None,
            float(row['debit']) if row['debit'] > 0 else None,
            balance,
            trans_hash,
            '2014-2017 CIBC 8362.xlsx',
            trans_hash
        ))
        
        if cur.rowcount > 0:
            imported += 1
        else:
            duplicates += 1
            
    except Exception as e:
        errors += 1
        print(f"❌ Error row {idx}: {e}")
        if errors > 10:
            print("Too many errors, stopping...")
            conn.rollback()
            sys.exit(1)

# COMMIT
conn.commit()
print(f"\n✅ COMMITTED to database")

print("\n" + "=" * 80)
print("IMPORT SUMMARY")
print("=" * 80)
print(f"✅ Imported:   {imported:,} new transactions")
print(f"⏭️  Duplicates: {duplicates:,} (skipped)")
print(f"❌ Errors:     {errors}")
print(f"📊 Total rows: {len(df):,}")

# Verify import
cur.execute("""
    SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date), 
           SUM(COALESCE(credit_amount, 0) - COALESCE(debit_amount, 0))
    FROM banking_transactions
    WHERE bank_id = 1
    AND transaction_date BETWEEN '2014-01-01' AND '2017-12-31'
""")
final_count, final_min, final_max, final_sum = cur.fetchone()

print("\n" + "=" * 80)
print("VERIFICATION")
print("=" * 80)
print(f"Database records (2014-2017, bank_id=1): {final_count:,}")
print(f"Date range: {final_min} to {final_max}")
print(f"Net amount: ${final_sum:,.2f}")

cur.close()
conn.close()

print("\n✅ Import complete - CIBC 0228362 (8362) 2014-2017 VERIFIED")
