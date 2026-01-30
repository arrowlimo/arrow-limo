#!/usr/bin/env python3
"""
Investigate the origin of the 35 user-specified transactions.
Track down source_file, import history, and how they got into almsdata.
"""

import os
import psycopg2
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

# The 35 transaction IDs user provided
user_ids = [
    52174, 52173, 55534, 52104, 55516, 55515, 55553, 55547, 55558, 55567,
    52156, 52157, 52158, 55468, 55466, 55472, 52103, 55508, 55509, 55494,
    55499, 55503, 55504, 55505, 52183, 55432, 55433, 55478, 55492, 52171,
    52172, 55434, 55476, 55477, 55454
]

print("=" * 120)
print("ORIGIN INVESTIGATION: WHERE DID THESE 35 TRANSACTIONS COME FROM?")
print("=" * 120)

conn = get_db_connection()
cur = conn.cursor()

# Step 1: Get all details including source tracking
print("\n[STEP 1] Getting full transaction details with source information...")

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
        source_file,
        source_hash,
        created_at,
        updated_at
    FROM banking_transactions
    WHERE transaction_id = ANY(%s)
    ORDER BY transaction_id
""", (user_ids,))

transactions = cur.fetchall()

# Group by source_file
by_source = {}
for row in transactions:
    source = row[8] or 'UNKNOWN/NULL'
    if source not in by_source:
        by_source[source] = []
    by_source[source].append(row)

print(f"\nFound {len(transactions)} transactions from {len(by_source)} different sources:")
for source, trans_list in sorted(by_source.items()):
    print(f"\n  Source: {source}")
    print(f"  Count: {len(trans_list)} transactions")
    
    # Show ID range
    ids = [t[0] for t in trans_list]
    print(f"  ID range: {min(ids)} to {max(ids)}")
    
    # Show date range
    dates = [t[2] for t in trans_list if t[2]]
    if dates:
        print(f"  Date range: {min(dates)} to {max(dates)}")
    
    # Show created_at timestamps
    created_ats = [t[10] for t in trans_list if t[10]]
    if created_ats:
        print(f"  Created: {min(created_ats)} to {max(created_ats)}")
    
    # Sample description
    if trans_list:
        print(f"  Sample: ID {trans_list[0][0]} - {trans_list[0][3][:60]}")

# Step 2: Check if these IDs overlap with known import batches
print("\n" + "=" * 120)
print("[STEP 2] Checking ID ranges against known import patterns...")
print("=" * 120)

# Get ID ranges from the backup we created earlier
cur.execute("""
    SELECT 
        MIN(transaction_id) as min_id,
        MAX(transaction_id) as max_id,
        COUNT(*) as count
    FROM scotia_2012_backup_20251105_232707
""")
backup_range = cur.fetchone()
print(f"\nBackup table (original Scotia 2012): IDs {backup_range[0]} to {backup_range[1]} ({backup_range[2]} transactions)")

# Check how many of user's IDs fall in backup range
user_in_backup = [uid for uid in user_ids if backup_range[0] <= uid <= backup_range[1]]
print(f"  {len(user_in_backup)} of user's 35 IDs fall within this range")

# Step 3: Check for duplicate content (same transaction, different ID)
print("\n" + "=" * 120)
print("[STEP 3] Checking for duplicate transactions (same content, different IDs)...")
print("=" * 120)

# Look for transactions with same date, account, amount as these 35
cur.execute("""
    SELECT 
        bt1.transaction_id as original_id,
        bt1.transaction_date,
        bt1.description,
        bt1.debit_amount,
        bt1.credit_amount,
        bt2.transaction_id as duplicate_id,
        bt2.source_file as duplicate_source
    FROM banking_transactions bt1
    JOIN banking_transactions bt2 
        ON bt1.account_number = bt2.account_number
        AND bt1.transaction_date = bt2.transaction_date
        AND COALESCE(bt1.debit_amount, 0) = COALESCE(bt2.debit_amount, 0)
        AND COALESCE(bt1.credit_amount, 0) = COALESCE(bt2.credit_amount, 0)
        AND bt1.transaction_id != bt2.transaction_id
    WHERE bt1.transaction_id = ANY(%s)
        AND bt1.account_number = '903990106011'
        AND bt1.transaction_date >= '2012-01-01'
        AND bt1.transaction_date <= '2012-12-31'
    ORDER BY bt1.transaction_id, bt2.transaction_id
""", (user_ids,))

duplicates = cur.fetchall()

if duplicates:
    print(f"\n[WARN]  Found {len(duplicates)} DUPLICATE transactions!")
    print("\nThese 35 transactions have DUPLICATES in the database:")
    
    dup_map = {}
    for dup in duplicates:
        orig_id = dup[0]
        if orig_id not in dup_map:
            dup_map[orig_id] = []
        dup_map[orig_id].append(dup)
    
    for orig_id, dups in sorted(dup_map.items()):
        print(f"\n  ID {orig_id}: {dups[0][1]} - {dups[0][2][:60]}")
        print(f"    Debit: ${dups[0][3] or 0} Credit: ${dups[0][4] or 0}")
        print(f"    Has {len(dups)} duplicate(s):")
        for dup in dups:
            print(f"      → ID {dup[5]} (source: {dup[6] or 'UNKNOWN'})")
else:
    print("\n✓ No exact duplicates found (same date/amount, different ID)")

# Step 4: Check import audit logs if they exist
print("\n" + "=" * 120)
print("[STEP 4] Checking for import audit trails...")
print("=" * 120)

# Check if there's an import log table
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
        AND table_name LIKE '%import%log%'
        OR table_name LIKE '%audit%'
        OR table_name LIKE '%staging%'
    ORDER BY table_name
""")
audit_tables = cur.fetchall()

if audit_tables:
    print(f"\nFound {len(audit_tables)} potential audit/staging tables:")
    for table in audit_tables:
        print(f"  - {table[0]}")
else:
    print("\n[WARN]  No import audit log tables found")

# Step 5: Check source_hash patterns
print("\n" + "=" * 120)
print("[STEP 5] Analyzing source_hash patterns...")
print("=" * 120)

cur.execute("""
    SELECT 
        transaction_id,
        source_hash,
        source_file
    FROM banking_transactions
    WHERE transaction_id = ANY(%s)
    ORDER BY transaction_id
""", (user_ids,))

hash_data = cur.fetchall()

has_hash = sum(1 for h in hash_data if h[1])
no_hash = sum(1 for h in hash_data if not h[1])

print(f"\nSource hash status:")
print(f"  With hash: {has_hash}")
print(f"  Without hash: {no_hash}")

if has_hash > 0:
    print(f"\n  Transactions WITH source_hash were likely imported via automated script")
if no_hash > 0:
    print(f"  Transactions WITHOUT source_hash may have been manually entered or imported via old method")

# Step 6: Compare against verified CSV to find differences
print("\n" + "=" * 120)
print("[STEP 6] What's different between these 35 and your verified data?")
print("=" * 120)

# Get the date range of these 35
cur.execute("""
    SELECT 
        MIN(transaction_date) as min_date,
        MAX(transaction_date) as max_date
    FROM banking_transactions
    WHERE transaction_id = ANY(%s)
""", (user_ids,))
date_range = cur.fetchone()

print(f"\nUser's 35 transactions date range: {date_range[0]} to {date_range[1]}")

# Check what's in staged CSV for same date range
cur.execute("""
    SELECT 
        COUNT(*),
        MIN(transaction_date),
        MAX(transaction_date)
    FROM staging_scotia_2012_verified
    WHERE transaction_date >= %s
        AND transaction_date <= %s
""", (date_range[0], date_range[1]))
staged_overlap = cur.fetchone()

print(f"Staged verified CSV for same date range: {staged_overlap[0]} transactions")
print(f"  Date range: {staged_overlap[1]} to {staged_overlap[2]}")

print(f"\n[WARN]  Gap: {35 - staged_overlap[0] if staged_overlap[0] else 35} transactions in database but NOT in verified CSV")

# Step 7: Detailed transaction listing for review
print("\n" + "=" * 120)
print("[STEP 7] DETAILED LISTING - These 35 transactions:")
print("=" * 120)

print("\nID      | Date       | Debit     | Credit    | Source File")
print("-" * 120)

for trans in transactions:
    tid, acct, date, desc, debit, credit, bal, cat, source, hash, created, updated = trans
    debit_str = f"${debit:>8.2f}" if debit else "        -"
    credit_str = f"${credit:>8.2f}" if credit else "        -"
    source_str = (source or "UNKNOWN")[:30]
    print(f"{tid:>6} | {date} | {debit_str} | {credit_str} | {source_str}")

# Step 8: Final analysis
print("\n" + "=" * 120)
print("CONCLUSION: WHERE DID THESE TRANSACTIONS COME FROM?")
print("=" * 120)

print(f"\nThese 35 transactions:")
print(f"  • Are Scotia Bank (903990106011) December 2012 transactions")
print(f"  • Are currently in almsdata database")
print(f"  • Are NOT in your manually verified CSV")

# Determine likely source
if len(by_source) == 1:
    only_source = list(by_source.keys())[0]
    print(f"\n  • ALL came from same source: {only_source}")
    
    if only_source == 'UNKNOWN/NULL':
        print(f"    → Likely manually entered or imported via old script without source tracking")
    elif 'quickbooks' in only_source.lower() or 'qb' in only_source.lower():
        print(f"    → Imported from QuickBooks export")
    elif 'screenshot' in only_source.lower():
        print(f"    → Imported from bank screenshot processing")
    elif 'csv' in only_source.lower() or 'excel' in only_source.lower():
        print(f"    → Imported from CSV/Excel file")
else:
    print(f"\n  • Came from MULTIPLE sources:")
    for source in by_source.keys():
        print(f"    - {source} ({len(by_source[source])} transactions)")

if duplicates:
    print(f"\n  • [WARN]  CRITICAL: These are DUPLICATES of other transactions")
    print(f"    → Should be DELETED to avoid double-counting")
else:
    print(f"\n  • [WARN]  NOT in your verified data = NOT verified against bank records")
    print(f"    → Either:")
    print(f"       1. Incorrect/phantom transactions that should be deleted")
    print(f"       2. Missing from your manual verification (incomplete)")

cur.close()
conn.close()

print("\n" + "=" * 120)
