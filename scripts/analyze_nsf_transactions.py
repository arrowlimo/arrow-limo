#!/usr/bin/env python
"""
Analyze NSF transactions to verify they are NOT duplicates.
NSF pattern: NSF charge + (optional reversal) + (optional successful retry)
This creates legitimate 2-3 transaction sequences that should NOT be deduplicated.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import timedelta

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=" * 120)
print("NSF TRANSACTION ANALYSIS")
print("=" * 120)

# Find all NSF-related transactions
print("\n1. LOCATING NSF TRANSACTIONS...")
cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        description,
        gross_amount,
        created_from_banking,
        source_hash,
        banking_transaction_id
    FROM receipts
    WHERE LOWER(description) LIKE '%nsf%'
    OR LOWER(vendor_name) LIKE '%nsf%'
    OR LOWER(description) LIKE '%non-sufficient%'
    OR LOWER(description) LIKE '%returned%'
    OR LOWER(description) LIKE '%reversal%'
    ORDER BY receipt_date, gross_amount
""")

nsf_receipts = cur.fetchall()
print(f"   Found {len(nsf_receipts):,} NSF-related receipt entries")

# Analyze patterns
print("\n2. ANALYZING NSF PATTERNS...")

# Group by (date, amount) to find transaction sequences
nsf_by_date_amount = {}
for receipt in nsf_receipts:
    key = (receipt['receipt_date'], float(receipt['gross_amount']))
    if key not in nsf_by_date_amount:
        nsf_by_date_amount[key] = []
    nsf_by_date_amount[key].append(receipt)

print(f"   Unique (date, amount) combinations: {len(nsf_by_date_amount):,}")

# Show multi-transaction sequences
sequences = {k: v for k, v in nsf_by_date_amount.items() if len(v) > 1}
print(f"   Sequences with multiple transactions: {len(sequences):,}")

if sequences:
    print("\n   MULTI-TRANSACTION NSF SEQUENCES:")
    print("   " + "-" * 115)
    
    for (date, amount), receipts in sorted(sequences.items(), key=lambda x: -x[1][0]['gross_amount'])[:20]:
        print(f"\n   Date: {date} | Amount: ${amount:,.2f}")
        print(f"   Transaction count: {len(receipts)}")
        
        for i, r in enumerate(receipts, 1):
            banking_info = f" (Banking ID: {r['banking_transaction_id']})" if r['banking_transaction_id'] else " (Manual)"
            print(f"     {i}. Receipt {r['receipt_id']}: {r['vendor_name'][:40]}")
            print(f"        Description: {(r['description'] or '')[:70]}")
            print(f"        Source: {'Banking' if r['created_from_banking'] else 'Manual'}{banking_info}")
            print(f"        Hash: {r['source_hash'][:16]}...")

# Now check if NSF transactions are appearing in the deduplication CSV
print("\n\n3. CHECKING DEDUPLICATION CSV FOR NSF ENTRIES...")

# Read the CSV to see if NSF transactions are flagged as duplicates
import csv

csv_file = "l:\\limo\\reports\\receipt_duplicates_20251207_000323.csv"

try:
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Find NSF-related duplicates
    nsf_duplicates = [r for r in rows if 'nsf' in r['vendor_1'].lower() or 'nsf' in r['vendor_2'].lower()]
    
    print(f"   NSF entries in deduplication CSV: {len(nsf_duplicates)}")
    
    if nsf_duplicates:
        print(f"\n   ⚠️  WARNING: Found {len(nsf_duplicates)} NSF pairs in duplicates list")
        print("   " + "-" * 115)
        
        for dup in nsf_duplicates[:20]:
            print(f"\n   Receipts {dup['receipt_1']} & {dup['receipt_2']}")
            print(f"     Vendor 1: {dup['vendor_1']}")
            print(f"     Vendor 2: {dup['vendor_2']}")
            print(f"     Amount 1: {dup['amount_1']} | Amount 2: {dup['amount_2']}")
            print(f"     Date 1: {dup['date_1']} | Date 2: {dup['date_2']} ({dup['date_diff_days']} days apart)")
            print(f"     Match: {dup['vendor_match_%']} | Diff: {dup['amount_diff_%']}")
            print(f"     Category: {dup['category']}")
    else:
        print("\n   ✅ NO NSF transactions flagged as duplicates - Good!")

except FileNotFoundError:
    print(f"   CSV file not found: {csv_file}")

# Verify specific NSF patterns
print("\n\n4. VERIFYING NSF TRANSACTION PATTERNS...")
print("   " + "-" * 115)

# Pattern 1: NSF + Reversal
cur.execute("""
    SELECT 
        DATE(receipt_date) as txn_date,
        gross_amount,
        COUNT(*) as count,
        STRING_AGG(DISTINCT description, ' | ') as descriptions
    FROM receipts
    WHERE (
        LOWER(description) LIKE '%nsf%'
        OR LOWER(vendor_name) LIKE '%nsf%'
    )
    GROUP BY DATE(receipt_date), gross_amount
    HAVING COUNT(*) >= 2
    ORDER BY COUNT(*) DESC, gross_amount DESC
""")

multi_nsf = cur.fetchall()
print(f"\n   NSF sequences (2+ transactions same date/amount): {len(multi_nsf)}")

for row in multi_nsf[:15]:
    print(f"\n   {row['txn_date']} | ${row['gross_amount']:,.2f} | {row['count']} transactions")
    print(f"     Descriptions: {row['descriptions']}")

# Pattern 2: Find retry sequences (NSF then successful)
print("\n\n5. FINDING RETRY SEQUENCES (NSF → SUCCESSFUL)...")
print("   " + "-" * 115)

cur.execute("""
    SELECT 
        r1.receipt_date as nsf_date,
        r1.gross_amount as nsf_amount,
        r1.description as nsf_desc,
        r2.receipt_date as retry_date,
        r2.description as retry_desc,
        (r2.receipt_date - r1.receipt_date) as days_apart
    FROM receipts r1
    JOIN receipts r2 ON r1.gross_amount = r2.gross_amount
        AND r2.receipt_date > r1.receipt_date
        AND (r2.receipt_date - r1.receipt_date) <= 14
    WHERE (LOWER(r1.description) LIKE '%nsf%' OR LOWER(r1.vendor_name) LIKE '%nsf%')
    AND (LOWER(r2.description) NOT LIKE '%nsf%' AND LOWER(r2.vendor_name) NOT LIKE '%nsf%')
    AND r1.vendor_name IS NOT NULL
    ORDER BY r1.gross_amount DESC
    LIMIT 20
""")

retry_sequences = cur.fetchall()
print(f"\n   Found {cur.rowcount} potential NSF → Retry sequences")

for row in retry_sequences[:15]:
    print(f"\n   Amount: ${row['nsf_amount']:,.2f}")
    print(f"     NSF ({row['nsf_date']}): {(row['nsf_desc'] or '')[:60]}")
    print(f"     Retry ({row['retry_date']}): {(row['retry_desc'] or '')[:60]} ({row['days_apart']} days later)")

# Export NSF analysis
print("\n\n6. EXPORTING NSF ANALYSIS FOR REVIEW...")
print("   " + "-" * 115)

import csv
from datetime import datetime

csv_file = f"l:\\limo\\reports\\nsf_transaction_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

with open(csv_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow([
        'receipt_1_id', 'receipt_1_date', 'receipt_1_vendor', 'receipt_1_desc',
        'receipt_1_amount', 'receipt_1_banking',
        'receipt_2_id', 'receipt_2_date', 'receipt_2_vendor', 'receipt_2_desc',
        'receipt_2_amount', 'receipt_2_banking',
        'sequence_type', 'days_apart'
    ])
    
    # Write multi-transaction same-day sequences
    for (date, amount), receipts in sorted(sequences.items(), key=lambda x: -x[1][0]['gross_amount']):
        if len(receipts) >= 2:
            for i in range(len(receipts) - 1):
                r1 = receipts[i]
                r2 = receipts[i + 1]
                days_diff = (r2['receipt_date'] - r1['receipt_date']).days
                
                # Determine sequence type
                has_nsf_1 = 'nsf' in (r1['description'] or '').lower() or 'nsf' in (r1['vendor_name'] or '').lower()
                has_nsf_2 = 'nsf' in (r2['description'] or '').lower() or 'nsf' in (r2['vendor_name'] or '').lower()
                
                if has_nsf_1 and not has_nsf_2:
                    seq_type = 'NSF_THEN_RETRY'
                elif has_nsf_1 and has_nsf_2:
                    seq_type = 'NSF_AND_REVERSAL'
                elif not has_nsf_1 and has_nsf_2:
                    seq_type = 'RETRY_THEN_NSF'
                else:
                    seq_type = 'UNKNOWN'
                
                writer.writerow([
                    r1['receipt_id'], r1['receipt_date'], r1['vendor_name'], r1['description'],
                    float(r1['gross_amount']), r1['created_from_banking'],
                    r2['receipt_id'], r2['receipt_date'], r2['vendor_name'], r2['description'],
                    float(r2['gross_amount']), r2['created_from_banking'],
                    seq_type, days_diff
                ])

print(f"\n   ✓ Exported to: {csv_file}")

# Summary
print("\n\n" + "=" * 120)
print("SUMMARY")
print("=" * 120)

print(f"\nNSF Findings:")
print(f"  Total NSF-related receipts: {len(nsf_receipts):,}")
print(f"  Multi-transaction sequences: {len(sequences):,}")
print(f"  NSF entries in dedup CSV: {len(nsf_duplicates) if 'nsf_duplicates' in locals() else 'N/A'}")
print(f"  NSF → Retry sequences: {len(retry_sequences)}")

print(f"\n✅ RECOMMENDATION:")
print(f"  NSF transactions should NOT be deduplicated.")
print(f"  Each represents a legitimate sequence:")
print(f"    1. NSF CHARGE: Initial failed payment attempt")
print(f"    2. REVERSAL (optional): Bank reverses the NSF charge")
print(f"    3. RETRY: Successful payment on retry")
print(f"  All should be kept as separate transactions for audit trail.")

conn.close()
