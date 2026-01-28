#!/usr/bin/env python3
"""
Analyze CIBC 8362 receipts for duplicates with other bank accounts.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("="*70)
print("CIBC 8362 DUPLICATE ANALYSIS")
print("="*70)

# Get all 8362 receipts
print("\n1. CIBC 8362 receipts created:")
cur.execute("""
    SELECT COUNT(DISTINCT r.receipt_id)
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.source_file = 'cibc 8362 all.csv'
""")
total_8362_receipts = cur.fetchone()[0]
print(f"   Total: {total_8362_receipts:,}")

# Find duplicates - same date and amount with receipts from OTHER sources
print("\n2. Finding potential duplicates (same date + amount):")
cur.execute("""
    WITH cibc_8362_receipts AS (
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.gross_amount
        FROM receipts r
        JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.source_file = 'cibc 8362 all.csv'
    )
    SELECT 
        c.receipt_date,
        c.gross_amount,
        COUNT(*) as duplicate_count,
        COUNT(DISTINCT CASE WHEN bt.source_file = 'cibc 8362 all.csv' THEN r.receipt_id END) as from_8362,
        COUNT(DISTINCT CASE WHEN bt.source_file != 'cibc 8362 all.csv' THEN r.receipt_id END) as from_other
    FROM cibc_8362_receipts c
    JOIN receipts r ON r.receipt_date = c.receipt_date AND r.gross_amount = c.gross_amount
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.receipt_id != c.receipt_id  -- exclude self
    GROUP BY c.receipt_date, c.gross_amount
    HAVING COUNT(*) > 0
    ORDER BY duplicate_count DESC
    LIMIT 20
""")

duplicates = cur.fetchall()
if duplicates:
    print(f"\n   Found {len(duplicates)} duplicate date+amount combinations:\n")
    print(f"   {'Date':<12} {'Amount':>12} {'Total':>8} {'From 8362':>12} {'From Other':>12}")
    print("   " + "-" * 65)
    
    total_dup_count = 0
    for date, amount, dup_count, from_8362, from_other in duplicates[:10]:
        print(f"   {date} ${amount:>10,.2f} {dup_count:>8} {from_8362:>12} {from_other:>12}")
        total_dup_count += dup_count
else:
    print("   No duplicates found")

# Count how many 8362 receipts have matches in other sources
print("\n3. CIBC 8362 receipts with potential duplicates:")
cur.execute("""
    SELECT COUNT(DISTINCT c8362.receipt_id)
    FROM receipts c8362
    JOIN banking_transactions bt8362 ON c8362.banking_transaction_id = bt8362.transaction_id
    WHERE bt8362.source_file = 'cibc 8362 all.csv'
    AND EXISTS (
        SELECT 1 FROM receipts r2
        JOIN banking_transactions bt2 ON r2.banking_transaction_id = bt2.transaction_id
        WHERE r2.receipt_date = c8362.receipt_date
        AND r2.gross_amount = c8362.gross_amount
        AND bt2.source_file != 'cibc 8362 all.csv'
        AND r2.receipt_id != c8362.receipt_id
    )
""")

dup_8362_count = cur.fetchone()[0]
print(f"   {dup_8362_count:,} CIBC 8362 receipts have duplicates in other accounts")
print(f"   {total_8362_receipts - dup_8362_count:,} CIBC 8362 receipts are unique")

# Show what other sources these duplicate
print("\n4. Which sources duplicate with CIBC 8362:")
cur.execute("""
    SELECT 
        bt2.source_file,
        COUNT(DISTINCT r2.receipt_id) as dup_receipts
    FROM receipts c8362
    JOIN banking_transactions bt8362 ON c8362.banking_transaction_id = bt8362.transaction_id
    JOIN receipts r2 ON r2.receipt_date = c8362.receipt_date AND r2.gross_amount = c8362.gross_amount
    JOIN banking_transactions bt2 ON r2.banking_transaction_id = bt2.transaction_id
    WHERE bt8362.source_file = 'cibc 8362 all.csv'
    AND bt2.source_file != 'cibc 8362 all.csv'
    AND r2.receipt_id != c8362.receipt_id
    GROUP BY bt2.source_file
    ORDER BY dup_receipts DESC
""")

print(f"\n   {'Source File':<50} {'Duplicate Receipts':>20}")
print("   " + "-" * 75)
for src, count in cur.fetchall():
    src_str = (src or 'NULL')[:48]
    print(f"   {src_str:<50} {count:>20,}")

print(f"\n{'='*70}")
print("RECOMMENDATION")
print("="*70)
print(f"""
CIBC 8362 appears to be a QuickBooks duplication issue where
the same transactions were imported from both:
  - The actual CIBC account (0228362, 8117, 4462, etc.)
  - AND the QB account 8362

You should DELETE the {dup_8362_count:,} CIBC 8362 receipts that have
duplicates in other sources, keeping only the receipts from the
actual bank account sources.

The {total_8362_receipts - dup_8362_count:,} unique CIBC 8362 receipts should be reviewed
manually to see if they're legitimate.
""")

cur.close()
conn.close()
