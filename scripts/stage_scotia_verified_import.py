#!/usr/bin/env python3
"""
Stage Scotia Bank 2012 verified data for review before replacing live data.

This script:
1. Creates staging table staging_scotia_2012_verified
2. Imports CSV data into staging table
3. Validates and analyzes staged data
4. Compares staged vs existing data
5. Generates reports for review

Does NOT modify live banking_transactions table.
"""

import os
import sys
import csv
import hashlib
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_values

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

print("=" * 80)
print("SCOTIA BANK 2012 VERIFIED DATA STAGING")
print("=" * 80)

conn = get_db_connection()
cur = conn.cursor()

# Step 1: Create staging table
print("\n[1] Creating staging table...")
cur.execute("""
    DROP TABLE IF EXISTS staging_scotia_2012_verified CASCADE;
    
    CREATE TABLE staging_scotia_2012_verified (
        staging_id SERIAL PRIMARY KEY,
        csv_transaction_id INTEGER,
        transaction_date DATE NOT NULL,
        description TEXT,
        debit_amount DECIMAL(12,2),
        credit_amount DECIMAL(12,2),
        source_hash VARCHAR(64),
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()
print("✓ Created staging_scotia_2012_verified table")

# Step 2: Load CSV data
csv_path = r'L:\limo\CIBC UPLOADS\scotiabank verified data.csv'
print(f"\n[2] Loading CSV: {csv_path}")

if not os.path.exists(csv_path):
    print(f"ERROR: File not found: {csv_path}")
    sys.exit(1)

transactions = []
with open(csv_path, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Parse transaction ID
        trans_id = None
        if row.get('Transaction ID'):
            try:
                trans_id = int(row['Transaction ID'])
            except ValueError:
                pass
        
        # Parse date (Excel serial number or MM/DD/YYYY format)
        date_str = row.get('Date', '').strip()
        if date_str.isdigit():
            # Excel serial date (days since 1900-01-01, with leap year bug)
            excel_date = int(date_str)
            # Excel treats 1900 as leap year (it wasn't), so dates after Feb 28, 1900 are off by 1
            if excel_date > 60:
                excel_date -= 1
            # Convert to Python date (1900-01-01 is day 1 in Excel)
            base_date = datetime(1899, 12, 30)  # Excel's epoch
            actual_date = base_date + timedelta(days=excel_date)
            date_str = actual_date.strftime('%Y-%m-%d')
        elif '/' in date_str:
            # MM/DD/YYYY format
            parts = date_str.split('/')
            if len(parts) == 3:
                date_str = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
        
        # Parse amounts
        debit = row.get('Debit', '').strip().replace('$', '').replace(',', '')
        credit = row.get('Credit', '').strip().replace('$', '').replace(',', '')
        debit = float(debit) if debit else None
        credit = float(credit) if credit else None
        
        description = row.get('Description', '').strip()
        
        # Generate hash for deduplication
        hash_input = f"903990106011|{date_str}|{description}|{debit}|{credit}"
        source_hash = hashlib.sha256(hash_input.encode()).hexdigest()
        
        transactions.append({
            'csv_id': trans_id,
            'date': date_str,
            'description': description,
            'debit': debit,
            'credit': credit,
            'hash': source_hash
        })

print(f"✓ Loaded {len(transactions)} transactions from CSV")

# Step 3: Insert into staging table
print("\n[3] Inserting into staging table...")
insert_data = [
    (t['csv_id'], t['date'], t['description'], t['debit'], t['credit'], t['hash'])
    for t in transactions
]

execute_values(cur, """
    INSERT INTO staging_scotia_2012_verified 
        (csv_transaction_id, transaction_date, description, debit_amount, credit_amount, source_hash)
    VALUES %s
""", insert_data)
conn.commit()
print(f"✓ Inserted {len(transactions)} rows into staging table")

# Step 4: Analyze staged data
print("\n[4] Analyzing staged data...")

# Date range
cur.execute("""
    SELECT 
        MIN(transaction_date) as min_date,
        MAX(transaction_date) as max_date,
        COUNT(*) as total_count,
        COUNT(DISTINCT transaction_date) as unique_dates
    FROM staging_scotia_2012_verified
""")
row = cur.fetchone()
print(f"  Date range: {row[0]} to {row[1]}")
print(f"  Total transactions: {row[2]:,}")
print(f"  Unique dates: {row[3]:,}")

# Amount totals
cur.execute("""
    SELECT 
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits,
        COUNT(CASE WHEN debit_amount IS NOT NULL THEN 1 END) as debit_count,
        COUNT(CASE WHEN credit_amount IS NOT NULL THEN 1 END) as credit_count
    FROM staging_scotia_2012_verified
""")
row = cur.fetchone()
print(f"  Total debits: ${row[0]:,.2f} ({row[2]:,} transactions)")
print(f"  Total credits: ${row[1]:,.2f} ({row[3]:,} transactions)")
print(f"  Net: ${(row[1] or 0) - (row[0] or 0):,.2f}")

# Check for duplicates in staged data
cur.execute("""
    SELECT source_hash, COUNT(*) as dup_count
    FROM staging_scotia_2012_verified
    GROUP BY source_hash
    HAVING COUNT(*) > 1
""")
staging_dups = cur.fetchall()
if staging_dups:
    print(f"\n  [WARN]  WARNING: {len(staging_dups)} duplicate hash(es) in staged data")
    for hash_val, count in staging_dups[:5]:
        print(f"      Hash {hash_val[:16]}... appears {count} times")
else:
    print(f"  ✓ No duplicates in staged data")

# Step 5: Compare with existing data
print("\n[5] Comparing staged vs existing data...")

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions
    WHERE account_number = '903990106011'
      AND transaction_date >= '2012-01-01'
      AND transaction_date <= '2012-12-31'
""")
existing_count = cur.fetchone()[0]
print(f"  Existing Scotia 2012: {existing_count:,} transactions")
print(f"  Staged verified: {len(transactions):,} transactions")
print(f"  Difference: {len(transactions) - existing_count:+,} transactions")

# Check for matching hashes (same transactions)
cur.execute("""
    SELECT COUNT(*)
    FROM staging_scotia_2012_verified s
    JOIN banking_transactions b 
        ON b.source_hash = s.source_hash
    WHERE b.account_number = '903990106011'
      AND b.transaction_date >= '2012-01-01'
      AND b.transaction_date <= '2012-12-31'
""")
matching_hashes = cur.fetchone()[0]
print(f"  Matching transactions (by hash): {matching_hashes:,}")
print(f"  New/changed transactions: {len(transactions) - matching_hashes:,}")

# Check payment links that would be affected
cur.execute("""
    SELECT COUNT(DISTINCT bpl.banking_transaction_id)
    FROM banking_payment_links bpl
    JOIN banking_transactions bt ON bt.transaction_id = bpl.banking_transaction_id
    WHERE bt.account_number = '903990106011'
      AND bt.transaction_date >= '2012-01-01'
      AND bt.transaction_date <= '2012-12-31'
""")
linked_count = cur.fetchone()[0]
if linked_count > 0:
    print(f"\n  [WARN]  WARNING: {linked_count} existing transactions have payment links")
    print(f"      These links will be deleted during replacement")

# Step 6: Generate comparison report
print("\n[6] Generating comparison reports...")

# Transactions only in existing (will be deleted)
cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.description,
        bt.debit_amount,
        bt.credit_amount
    FROM banking_transactions bt
    WHERE bt.account_number = '903990106011'
      AND bt.transaction_date >= '2012-01-01'
      AND bt.transaction_date <= '2012-12-31'
      AND NOT EXISTS (
          SELECT 1 FROM staging_scotia_2012_verified s
          WHERE s.source_hash = bt.source_hash
      )
    ORDER BY bt.transaction_date, bt.transaction_id
""")
only_existing = cur.fetchall()

if only_existing:
    report_path = 'reports/scotia_2012_to_be_deleted.csv'
    os.makedirs('reports', exist_ok=True)
    with open(report_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Transaction ID', 'Date', 'Description', 'Debit', 'Credit'])
        for row in only_existing:
            writer.writerow(row)
    print(f"  ✓ Transactions to be deleted: {report_path} ({len(only_existing)} rows)")
else:
    print(f"  ✓ No transactions will be deleted (all existing have matches)")

# Transactions only in staged (will be added)
cur.execute("""
    SELECT 
        s.csv_transaction_id,
        s.transaction_date,
        s.description,
        s.debit_amount,
        s.credit_amount
    FROM staging_scotia_2012_verified s
    WHERE NOT EXISTS (
        SELECT 1 FROM banking_transactions bt
        WHERE bt.source_hash = s.source_hash
          AND bt.account_number = '903990106011'
          AND bt.transaction_date >= '2012-01-01'
          AND bt.transaction_date <= '2012-12-31'
    )
    ORDER BY s.transaction_date, s.staging_id
""")
only_staged = cur.fetchall()

if only_staged:
    report_path = 'reports/scotia_2012_to_be_added.csv'
    with open(report_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['CSV Trans ID', 'Date', 'Description', 'Debit', 'Credit'])
        for row in only_staged:
            writer.writerow(row)
    print(f"  ✓ Transactions to be added: {report_path} ({len(only_staged)} rows)")
else:
    print(f"  ✓ No new transactions (all staged already exist)")

print("\n" + "=" * 80)
print("STAGING COMPLETE")
print("=" * 80)
print("\nNext steps:")
print("  1. Review reports/scotia_2012_to_be_deleted.csv")
print("  2. Review reports/scotia_2012_to_be_added.csv")
print("  3. Run: python scripts/apply_scotia_verified_import.py")
print("     (This will perform the actual replacement)")

cur.close()
conn.close()
