#!/usr/bin/env python3
"""
INVESTIGATE 1,275 CHARTERS WITH DOUBLE PAYMENTS
================================================

Deeper analysis of charters with payments in BOTH Neon and local
to determine which are true duplicates vs legitimate additional payments.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from collections import defaultdict
import json

from dotenv import load_dotenv
load_dotenv()

print("="*80)
print("INVESTIGATING CHARTERS WITH PAYMENTS IN BOTH DATABASES")
print("="*80)

local_conn = psycopg2.connect(
    host='localhost',
    database=os.getenv('LOCAL_DB_NAME'),
    user=os.getenv('LOCAL_DB_USER'),
    password=os.getenv('LOCAL_DB_PASSWORD'),
    cursor_factory=RealDictCursor
)

neon_conn = psycopg2.connect(
    host=os.getenv('NEON_DB_HOST'),
    database=os.getenv('NEON_DB_NAME'),
    user=os.getenv('NEON_DB_USER'),
    password=os.getenv('NEON_DB_PASSWORD'),
    sslmode='require',
    cursor_factory=RealDictCursor
)

# Get all local-only payments
local_cur = local_conn.cursor()
neon_cur = neon_conn.cursor()

# Get Neon payment IDs
neon_cur.execute("SELECT payment_id FROM payments")
neon_ids = set(row['payment_id'] for row in neon_cur.fetchall())

# Get local-only payments
local_cur.execute("""
    SELECT payment_id, reserve_number, amount, payment_date, payment_method, created_at
    FROM payments
    ORDER BY payment_id
""")
all_local = local_cur.fetchall()
local_only_payments = [p for p in all_local if p['payment_id'] not in neon_ids]

print(f"✅ Analyzing {len(local_only_payments):,} local-only payments\n")

# Group by reserve_number  
by_reserve = defaultdict(list)
for p in local_only_payments:
    if p['reserve_number']:
        by_reserve[p['reserve_number']].append(p)

# Get reserves that have payments in Neon
neon_cur.execute("""
    SELECT DISTINCT c.reserve_number, c.charter_id, c.total_amount_due
    FROM charters c
    INNER JOIN payments p ON p.charter_id = c.charter_id
""")
neon_reserve_charters = {row['reserve_number']: row for row in neon_cur.fetchall()}

# Find overlapping reserves
overlapping_reserves = set(by_reserve.keys()) & set(neon_reserve_charters.keys())

print(f"🔍 Found {len(overlapping_reserves):,} charters with payments in BOTH databases")
print()

# Get ALL Neon payments for overlapping charters at once
charter_ids = [neon_reserve_charters[r]['charter_id'] for r in overlapping_reserves]

print("Loading all Neon payments for overlapping charters...")
neon_cur.execute("""
    SELECT p.payment_id, p.charter_id, c.reserve_number, p.amount, p.payment_date, 
           p.payment_method, p.created_at, p.square_transaction_id
    FROM payments p
    INNER JOIN charters c ON c.charter_id = p.charter_id
    WHERE p.charter_id = ANY(%s)
    ORDER BY c.reserve_number, p.payment_date, p.payment_id
""", (charter_ids,))

all_neon_payments = neon_cur.fetchall()
print(f"✅ Loaded {len(all_neon_payments):,} Neon payments")

# Index by reserve_number
neon_payments_by_reserve = defaultdict(list)
for p in all_neon_payments:
    neon_payments_by_reserve[p['reserve_number']].append(p)

# Deep dive into each overlapping reserve
analysis = []

for reserve_num in sorted(list(overlapping_reserves)):
    charter_info = neon_reserve_charters[reserve_num]
    charter_id = charter_info['charter_id']
    total_due = charter_info['total_amount_due']
    
    # Get Neon payments for this charter (from our preloaded data)
    neon_payments = neon_payments_by_reserve[reserve_num]
    
    # Get local payments for this reserve
    local_payments = by_reserve[reserve_num]
    
    # Calculate totals
    neon_total = sum(p['amount'] or 0 for p in neon_payments)
    local_total = sum(p['amount'] or 0 for p in local_payments)
    
    # Compare payment details
    exact_duplicates = 0
    possible_additional = 0
    
    for local_pmt in local_payments:
        # Check if this exact payment exists in Neon
        match_found = False
        for neon_pmt in neon_payments:
            if (local_pmt['amount'] == neon_pmt['amount'] and
                local_pmt['payment_date'] == neon_pmt['payment_date']):
                exact_duplicates += 1
                match_found = True
                break
        
        if not match_found:
            possible_additional += 1
    
    # Determine classification
    if exact_duplicates == len(local_payments) and abs(local_total - neon_total) < 0.01:
        classification = "EXACT_DUPLICATE"
    elif exact_duplicates > 0:
        classification = "PARTIAL_DUPLICATE" 
    elif abs(local_total - neon_total) < 0.01:
        classification = "SAME_TOTAL_DIFFERENT_BREAKDOWN"
    elif total_due and abs((neon_total + local_total) - total_due) < 0.01:
        classification = "COMPLEMENTARY_PAYMENTS"
    elif local_total < neon_total:
        classification = "LOCAL_SUBSET"
    else:
        classification = "NEEDS_REVIEW"
    
    analysis.append({
        'reserve_number': reserve_num,
        'charter_id': charter_id,
        'total_due': float(total_due) if total_due else None,
        'neon_payment_count': len(neon_payments),
        'neon_total': float(neon_total),
        'local_payment_count': len(local_payments),
        'local_total': float(local_total),
        'exact_duplicates': exact_duplicates,
        'possible_additional': possible_additional,
        'classification': classification,
        'local_payment_ids': [p['payment_id'] for p in local_payments],
        'local_payment_methods': [p['payment_method'] for p in local_payments],
        'neon_has_square': any(p.get('square_transaction_id') for p in neon_payments)
    })

# Group by classification
by_class = defaultdict(list)
for item in analysis:
    by_class[item['classification']].append(item)

print("="*80)
print("CLASSIFICATION RESULTS")
print("="*80)

for classification, items in sorted(by_class.items(), key=lambda x: -len(x[1])):
    count = len(items)
    total_local_pmts = sum(item['local_payment_count'] for item in items)
    
    print(f"\n{classification}: {count:,} charters ({total_local_pmts:,} local payments)")
    
    # Show samples
    for item in items[:3]:
        print(f"  Reserve {item['reserve_number']}: "
              f"Neon={item['neon_payment_count']} (${item['neon_total']:,.2f}) | "
              f"Local={item['local_payment_count']} (${item['local_total']:,.2f})")
    
    if len(items) > 3:
        print(f"  ... and {len(items) - 3} more")

# Determine safe deletions
safe_to_delete_ids = []

for item in by_class['EXACT_DUPLICATE']:
    safe_to_delete_ids.extend(item['local_payment_ids'])

print()
print("="*80)
print("DELETION RECOMMENDATIONS")
print("="*80)
print(f"\n✅ EXACT_DUPLICATE: Can safely delete {len(safe_to_delete_ids):,} local payments")
print(f"   These are identical to payments already in Neon")

other_classifications = [k for k in by_class.keys() if k != 'EXACT_DUPLICATE']
if other_classifications:
    print(f"\n⚠️  Other classifications need manual review:")
    for classification in other_classifications:
        count = sum(item['local_payment_count'] for item in by_class[classification])
        print(f"   {classification}: {count:,} payments")

# Save analysis
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
report_file = f"double_payment_analysis_{timestamp}.json"

with open(report_file, 'w') as f:
    json.dump({
        'timestamp': datetime.now().isoformat(),
        'total_overlapping_charters': len(overlapping_reserves),
        'classifications': {k: len(v) for k, v in by_class.items()},
        'safe_to_delete_count': len(safe_to_delete_ids),
        'safe_to_delete_ids': safe_to_delete_ids,
        'analysis': analysis
    }, f, indent=2, default=str)

print(f"\n📄 Detailed analysis saved: {report_file}")

# Create deletion script for exact duplicates
if safe_to_delete_ids:
    sql_file = f"delete_exact_duplicate_payments_{timestamp}.sql"
    with open(sql_file, 'w') as f:
        f.write("-- DELETE EXACT DUPLICATE PAYMENTS\n")
        f.write(f"-- These payments are identical to payments already in Neon\n")
        f.write(f"-- Count: {len(safe_to_delete_ids):,}\n\n")
        f.write("BEGIN;\n\n")
        f.write("DELETE FROM payments WHERE payment_id IN (\n")
        
        batch_size = 100
        batches = [safe_to_delete_ids[i:i+batch_size] for i in range(0, len(safe_to_delete_ids), batch_size)]
        for i, batch in enumerate(batches):
            f.write(f"  {', '.join(map(str, batch))}")
            if i < len(batches) - 1:
                f.write(",\n")
            else:
                f.write("\n")
        
        f.write(");\n\n")
        f.write(f"-- Expected: {len(safe_to_delete_ids):,} rows deleted\n\n")
        f.write("-- COMMIT;  -- Uncomment to commit\n")
        f.write("ROLLBACK;  -- Remove when ready\n")
    
    print(f"📄 Deletion SQL saved: {sql_file}")

local_conn.close()
neon_conn.close()

print("\n✅ Analysis complete")
