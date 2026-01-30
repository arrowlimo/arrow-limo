#!/usr/bin/env python
"""
Standardize vendors in banking_transactions, match to receipts, find missing transactions.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password=os.environ.get('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Define vendor standardization rules (current → standardized)
VENDOR_STANDARDS = {
    # Auto/Maintenance
    "Eries Auto Repair": ["Erles Auto Repair"],
    "Canadian Tire": ["CanadianT ire"],
    
    # Fuel vendors (already clean)
    "Centex": ["CENTEX", "Centex Deerpark"],
    "Fas Gas": ["FAS GAS", "Fas Gas Station"],
    "Shell": ["SHELL"],
    "Husky": ["HUSKY"],
    "Esso": ["ESSO"],
    "Domo Gas": ["DOMO"],
    
    # Liquor stores (consolidate variants)
    "Uptown Liquor": ["UPTOWN LIQUOR", "Up Town Liquor Store"],
    "One Stop Liquor": ["ONE STOP LIQUOR"],
    "Liquor 7": ["LIQUOR 7"],
    "Liquor Barn": ["Llq(!Or Barn", "Liquor Barn 67th"],
    
    # Other key vendors
    "Staples": ["STAPLES"],
    "Tim Hortons": ["TIM HORTONS"],
    "Phil's Restaurant": ["PHILLIS", "Phils Restaurant"],
    "Co-op": ["Co", "CO-OP"],
}

print("=" * 100)
print("STEP 1: STANDARDIZING VENDOR NAMES IN BANKING_TRANSACTIONS")
print("=" * 100)

# Create backup
backup_table = f"banking_transactions_vendor_standardization_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM banking_transactions WHERE account_number = '0228362'")
conn.commit()
print(f"\n✓ Backup created: {backup_table} ({cur.rowcount:,} rows)")

# Apply standardization rules
total_updates = 0
for standard_name, variants in VENDOR_STANDARDS.items():
    for variant in variants:
        cur.execute(
            """
            UPDATE banking_transactions
            SET vendor_extracted = %s
            WHERE vendor_extracted = %s
            AND account_number = '0228362'
            """,
            (standard_name, variant)
        )
        if cur.rowcount > 0:
            print(f"  ✓ '{variant}' → '{standard_name}': {cur.rowcount} rows")
            total_updates += cur.rowcount

conn.commit()
print(f"\n✓ Total vendor updates: {total_updates}")

# Get updated vendor list
print("\n" + "=" * 100)
print("STEP 2: MATCHING RECEIPTS TO BANKING TRANSACTIONS")
print("=" * 100)

# Strategy 1: Exact vendor + amount + date
cur.execute("""
    SELECT COUNT(*) as matches
    FROM receipts r
    JOIN banking_transactions bt ON 
        LOWER(REPLACE(r.vendor_name, '.', '')) = LOWER(REPLACE(bt.vendor_extracted, '.', ''))
        AND r.gross_amount = bt.debit_amount
        AND r.receipt_date = bt.transaction_date
    WHERE bt.account_number = '0228362'
    AND r.banking_transaction_id IS NULL
""")
exact_matches = cur.fetchone()['matches']
print(f"\n1. Exact match (vendor + amount + date): {exact_matches} receipts")

# Link exact matches
cur.execute("""
    UPDATE receipts r
    SET banking_transaction_id = bt.transaction_id
    FROM banking_transactions bt
    WHERE LOWER(REPLACE(r.vendor_name, '.', '')) = LOWER(REPLACE(bt.vendor_extracted, '.', ''))
    AND r.gross_amount = bt.debit_amount
    AND r.receipt_date = bt.transaction_date
    AND bt.account_number = '0228362'
    AND r.banking_transaction_id IS NULL
""")
conn.commit()
print(f"  ✓ Linked {cur.rowcount} receipts to banking transactions")

# Strategy 2: Vendor + amount within ±3 days
cur.execute("""
    SELECT COUNT(*) as matches
    FROM receipts r
    JOIN banking_transactions bt ON 
        LOWER(REPLACE(r.vendor_name, '.', '')) = LOWER(REPLACE(bt.vendor_extracted, '.', ''))
        AND r.gross_amount = bt.debit_amount
        AND (r.receipt_date - bt.transaction_date) BETWEEN -3 AND 3
    WHERE bt.account_number = '0228362'
    AND r.banking_transaction_id IS NULL
""")
near_matches = cur.fetchone()['matches']
print(f"\n2. Near date match (vendor + amount ±3 days): {near_matches} receipts")

# Link near matches
cur.execute("""
    UPDATE receipts r
    SET banking_transaction_id = bt.transaction_id
    FROM banking_transactions bt
    WHERE LOWER(REPLACE(r.vendor_name, '.', '')) = LOWER(REPLACE(bt.vendor_extracted, '.', ''))
    AND r.gross_amount = bt.debit_amount
    AND (r.receipt_date - bt.transaction_date) BETWEEN -3 AND 3
    AND bt.account_number = '0228362'
    AND r.banking_transaction_id IS NULL
""")
conn.commit()
print(f"  ✓ Linked {cur.rowcount} receipts to banking transactions")

# Get match statistics
print("\n" + "=" * 100)
print("STEP 3: RECEIPT-BANKING MATCH STATISTICS")
print("=" * 100)

cur.execute("""
    SELECT 
        COUNT(*) as total_receipts,
        COUNT(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 END) as matched,
        COUNT(CASE WHEN banking_transaction_id IS NULL THEN 1 END) as unmatched
    FROM receipts
    WHERE vendor_name NOT IN ('Banking', 'Square', 'Unknown', 'Customer')
    AND gross_amount > 0
""")

stats = cur.fetchone()
print(f"\nReceipt Statistics:")
print(f"  Total receipts: {stats['total_receipts']:,}")
print(f"  Matched to banking: {stats['matched']:,} ({100*stats['matched']/stats['total_receipts']:.1f}%)")
print(f"  Unmatched: {stats['unmatched']:,} ({100*stats['unmatched']/stats['total_receipts']:.1f}%)")

# Get banking match statistics
cur.execute("""
    SELECT 
        COUNT(*) as total_debits,
        COUNT(CASE WHEN receipt_id IS NOT NULL THEN 1 END) as with_receipt,
        COUNT(CASE WHEN receipt_id IS NULL THEN 1 END) as without_receipt
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND debit_amount > 0
""")

bank_stats = cur.fetchone()
print(f"\nBanking Statistics:")
print(f"  Total debit transactions: {bank_stats['total_debits']:,}")
print(f"  With receipt: {bank_stats['with_receipt']:,} ({100*bank_stats['with_receipt']/bank_stats['total_debits']:.1f}%)")
print(f"  Without receipt: {bank_stats['without_receipt']:,} ({100*bank_stats['without_receipt']/bank_stats['total_debits']:.1f}%)")

# Find missing banking transactions (no matching receipt)
print("\n" + "=" * 100)
print("STEP 4: MISSING BANKING TRANSACTIONS (WITHOUT RECEIPTS)")
print("=" * 100)

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        vendor_extracted,
        debit_amount,
        description
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND debit_amount > 0
    AND receipt_id IS NULL
    ORDER BY debit_amount DESC
    LIMIT 50
""")

missing = cur.fetchall()
print(f"\nTop 50 missing banking transactions (highest value first):\n")

total_missing = 0
for i, txn in enumerate(missing, 1):
    vendor = txn['vendor_extracted'] or 'Unknown'
    print(f"{i:3}. {txn['transaction_date']} | {vendor:40} | ${txn['debit_amount']:10,.2f}")
    total_missing += txn['debit_amount']

# Get total for all missing
cur.execute("""
    SELECT 
        COUNT(*) as count,
        ROUND(SUM(debit_amount)::numeric, 2) as total
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND debit_amount > 0
    AND receipt_id IS NULL
""")

all_missing = cur.fetchone()
print(f"\n{'-' * 100}")
print(f"Total missing banking transactions: {all_missing['count']:,} | Total value: ${all_missing['total']:,.2f}")
print("=" * 100)

# Export missing transactions to CSV
import csv
csv_path = f"l:\\limo\\reports\\missing_banking_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        vendor_extracted,
        description,
        debit_amount,
        credit_amount,
        balance
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND debit_amount > 0
    AND receipt_id IS NULL
    ORDER BY debit_amount DESC
""")

with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
    fieldnames = ['transaction_id', 'transaction_date', 'vendor_extracted', 'description', 
                  'debit_amount', 'credit_amount', 'balance']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for row in cur.fetchall():
        writer.writerow(row)

print(f"\n✓ Exported missing transactions to: {csv_path}")

conn.close()
print("\n" + "=" * 100)
print("✓ STANDARDIZATION AND MATCHING COMPLETE")
print("=" * 100 + "\n")
