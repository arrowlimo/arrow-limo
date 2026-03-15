#!/usr/bin/env python3
"""
PAYMENT TABLE CLEANUP - STEP-BY-STEP DEDUPLICATION
===================================================

STEP 1: Mark Neon payments as PROTECTED (do not delete)
STEP 2: Deduplicate local payments
STEP 3: Compare by reserve_number for deletion candidates
STEP 4: Identify QB contamination and Square doubling
STEP 5: Note Scotiabank multi-client payment issue (already fixed in Neon)
STEP 6: Assess remaining unmatched payments
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
print("PAYMENT TABLE CLEANUP ANALYSIS")
print("="*80)
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# Connect to both databases
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

cleanup_report = {
    "timestamp": datetime.now().isoformat(),
    "protected_payments": [],
    "duplicate_groups": [],
    "qb_contamination": [],
    "square_doubling": [],
    "deletion_candidates": [],
    "safe_to_keep": [],
    "needs_review": []
}

# ============================================================================
# STEP 1: IDENTIFY NEON PAYMENTS - MARK AS PROTECTED
# ============================================================================
print("="*80)
print("STEP 1: IDENTIFY PROTECTED PAYMENTS (EXISTS IN NEON)")
print("="*80)

neon_cur = neon_conn.cursor()
neon_cur.execute("SELECT payment_id FROM payments ORDER BY payment_id")
neon_payment_ids = set(row['payment_id'] for row in neon_cur.fetchall())

print(f"✅ Neon has {len(neon_payment_ids):,} payment_ids")
print(f"   Range: {min(neon_payment_ids)} to {max(neon_payment_ids)}")

local_cur = local_conn.cursor()
local_cur.execute("SELECT payment_id FROM payments ORDER BY payment_id")
local_payment_ids = set(row['payment_id'] for row in local_cur.fetchall())

print(f"✅ Local has {len(local_payment_ids):,} payment_ids")
print(f"   Range: {min(local_payment_ids)} to {max(local_payment_ids)}")

# Find protected payments (exist in Neon)
protected_ids = neon_payment_ids & local_payment_ids
print(f"\n🛡️  PROTECTED (in both databases): {len(protected_ids):,} payments")
print(f"   → These will NOT be deleted from local")

cleanup_report['protected_payments'] = sorted(list(protected_ids))

# Find local-only payments
local_only_ids = local_payment_ids - neon_payment_ids
print(f"\n📋 LOCAL-ONLY payments: {len(local_only_ids):,} payments")
print(f"   → These are candidates for deduplication/cleanup")

print()

# ============================================================================
# STEP 2: DEDUPLICATE BY EXACT MATCH (reserve + amount + date)
# ============================================================================
print("="*80)
print("STEP 2: IDENTIFY DUPLICATE PAYMENTS")
print("="*80)

print("Loading all local-only payments...")
local_cur.execute("""
    SELECT payment_id, reserve_number, amount, payment_date, 
           payment_method, created_at, notes
    FROM payments
    WHERE payment_id = ANY(%s)
    ORDER BY payment_id
""", (sorted(list(local_only_ids)),))

local_only_payments = local_cur.fetchall()
print(f"✅ Loaded {len(local_only_payments):,} local-only payments")

# Group by exact match: reserve + amount + date
print("\nGrouping by (reserve_number, amount, payment_date)...")
dup_groups = defaultdict(list)

for payment in local_only_payments:
    # Create deduplication key
    key = (
        payment['reserve_number'],
        float(payment['amount']) if payment['amount'] else None,
        payment['payment_date']
    )
    dup_groups[key].append(payment)

# Find duplicate groups (2+ payments with same key)
duplicates = {k: v for k, v in dup_groups.items() if len(v) > 1}

print(f"\n🔍 Found {len(duplicates):,} duplicate groups:")
print(f"   Total payments in duplicates: {sum(len(v) for v in duplicates.values()):,}")

# Sort by number of duplicates
sorted_dups = sorted(duplicates.items(), key=lambda x: -len(x[1]))

print(f"\n   Top 20 duplicate groups:")
print(f"   {'Reserve':>8} {'Amount':>12} {'Date':>12} {'Count':>6} {'Payment IDs'}")
print(f"   {'-'*70}")

for (reserve, amount, date), payments in sorted_dups[:20]:
    pids = [p['payment_id'] for p in payments]
    reserve_str = reserve if reserve else 'NULL'
    amount_str = f"${amount:,.2f}" if amount else 'NULL'
    date_str = str(date) if date else 'NULL'
    print(f"   {reserve_str:>8} {amount_str:>12} {date_str:>12} {len(payments):>6} {pids}")

if len(sorted_dups) > 20:
    print(f"   ... and {len(sorted_dups) - 20} more groups")

# Save duplicate groups
cleanup_report['duplicate_groups'] = [
    {
        'reserve_number': k[0],
        'amount': float(k[1]) if k[1] else None,
        'payment_date': str(k[2]) if k[2] else None,
        'count': len(v),
        'payment_ids': [p['payment_id'] for p in v],
        'keep_first': v[0]['payment_id'],
        'delete_others': [p['payment_id'] for p in v[1:]]
    }
    for k, v in sorted_dups
]

total_duplicates_to_delete = sum(len(v) - 1 for v in duplicates.values())
print(f"\n⚠️  DEDUPLICATION PLAN:")
print(f"   Keep: {len(duplicates):,} payments (first of each group)")
print(f"   Delete: {total_duplicates_to_delete:,} duplicate payments")

print()

# ============================================================================
# STEP 3: COMPARE BY RESERVE_NUMBER WITH NEON
# ============================================================================
print("="*80)
print("STEP 3: COMPARE BY RESERVE_NUMBER WITH NEON")
print("="*80)

print("Checking which reserves have payments in Neon...")

# Get unique reserve numbers from local-only
unique_reserves = set(p['reserve_number'] for p in local_only_payments if p['reserve_number'])
print(f"✅ Local-only payments reference {len(unique_reserves):,} unique reserves")

# Check which reserves have payments in Neon
neon_cur.execute("""
    SELECT DISTINCT c.reserve_number, c.charter_id
    FROM charters c
    INNER JOIN payments p ON p.charter_id = c.charter_id
    WHERE c.reserve_number = ANY(%s)
""", (list(unique_reserves),))

reserves_with_neon_payments = {row['reserve_number']: row['charter_id'] for row in neon_cur.fetchall()}

print(f"✅ {len(reserves_with_neon_payments):,} reserves already have payments in Neon")
print(f"   {len(unique_reserves) - len(reserves_with_neon_payments):,} reserves have NO payments in Neon yet")

# For reserves with Neon payments, get details
print("\nAnalyzing reserves with payments already in Neon...")
reserve_comparison = []

for reserve_num in sorted(list(reserves_with_neon_payments.keys()))[:100]:  # Sample first 100
    charter_id = reserves_with_neon_payments[reserve_num]
    
    # Get Neon payment count and total
    neon_cur.execute("""
        SELECT COUNT(*) as count, SUM(amount) as total
        FROM payments
        WHERE charter_id = %s
    """, (charter_id,))
    neon_data = neon_cur.fetchone()
    
    # Get local-only payment count and total
    local_payments_for_reserve = [p for p in local_only_payments if p['reserve_number'] == reserve_num]
    local_count = len(local_payments_for_reserve)
    local_total = sum(p['amount'] or 0 for p in local_payments_for_reserve)
    
    reserve_comparison.append({
        'reserve_number': reserve_num,
        'charter_id': charter_id,
        'neon_count': neon_data['count'],
        'neon_total': float(neon_data['total'] or 0),
        'local_only_count': local_count,
        'local_only_total': float(local_total),
        'local_payment_ids': [p['payment_id'] for p in local_payments_for_reserve]
    })

# Sort by most local-only payments
reserve_comparison.sort(key=lambda x: -x['local_only_count'])

print(f"\n   Top 20 reserves with BOTH Neon and local-only payments:")
print(f"   {'Reserve':>8} {'Neon Pmts':>10} {'Local-Only':>12} {'Likely Status'}")
print(f"   {'-'*60}")

for item in reserve_comparison[:20]:
    # Determine likely status
    if item['local_only_count'] == item['neon_count']:
        status = "DUPLICATE (QB/Square)"
    elif item['local_only_count'] > item['neon_count']:
        status = "PARTIAL DUPLICATE"
    else:
        status = "NEEDS REVIEW"
    
    print(f"   {item['reserve_number']:>8} {item['neon_count']:>10} {item['local_only_count']:>12} {status}")

print()

# ============================================================================
# STEP 4: IDENTIFY QB CONTAMINATION & SQUARE DOUBLING
# ============================================================================
print("="*80)
print("STEP 4: IDENTIFY QB CONTAMINATION & SQUARE DOUBLING")
print("="*80)

qb_contamination = []
square_doubling = []

print("Analyzing payment patterns...")

for item in reserve_comparison:
    reserve_num = item['reserve_number']
    local_payments = [p for p in local_only_payments if p['reserve_number'] == reserve_num]
    
    # Check for QB contamination pattern:
    # - payment_method = 'unknown'
    # - created_at dates suggest QB import
    # - reserve already has correct payment in Neon
    
    qb_pattern_count = sum(1 for p in local_payments if p['payment_method'] == 'unknown')
    
    if qb_pattern_count == len(local_payments) and item['neon_count'] > 0:
        # All local payments are 'unknown' method AND Neon has payments
        # This is likely QB contamination
        qb_contamination.append({
            'reserve_number': reserve_num,
            'charter_id': item['charter_id'],
            'contaminated_count': len(local_payments),
            'payment_ids': [p['payment_id'] for p in local_payments],
            'reason': 'QuickBooks import duplicates - Neon has correct data'
        })
    
    # Check for Square doubling pattern:
    # - Multiple payments with same amount on same date
    # - payment_method might be 'credit_card'
    
    date_amount_groups = defaultdict(list)
    for p in local_payments:
        key = (p['payment_date'], p['amount'])
        date_amount_groups[key].append(p)
    
    for (date, amount), pmts in date_amount_groups.items():
        if len(pmts) >= 2:
            square_doubling.append({
                'reserve_number': reserve_num,
                'date': str(date) if date else None,
                'amount': float(amount) if amount else None,
                'duplicate_count': len(pmts),
                'payment_ids': [p['payment_id'] for p in pmts],
                'reason': 'Same amount/date - likely Square sync duplication'
            })

print(f"🔴 QB CONTAMINATION: {len(qb_contamination)} reserves")
print(f"   Total contaminated payments: {sum(item['contaminated_count'] for item in qb_contamination):,}")

if qb_contamination[:5]:
    print(f"\n   Sample QB contaminated reserves:")
    for item in qb_contamination[:5]:
        print(f"   - Reserve {item['reserve_number']}: {item['contaminated_count']} payments → DELETE")

print(f"\n🔴 SQUARE DOUBLING: {len(square_doubling)} instances")
if square_doubling[:5]:
    print(f"\n   Sample Square duplicates:")
    for item in square_doubling[:5]:
        print(f"   - Reserve {item['reserve_number']}: {item['duplicate_count']} x ${item['amount']} on {item['date']}")

cleanup_report['qb_contamination'] = qb_contamination
cleanup_report['square_doubling'] = square_doubling

print()

# ============================================================================
# STEP 5: NOTE SCOTIABANK MULTI-CLIENT PAYMENT ISSUE
# ============================================================================
print("="*80)
print("STEP 5: SCOTIABANK MULTI-CLIENT PAYMENT ISSUE")
print("="*80)

print("✅ ALREADY FIXED IN NEON:")
print("   - Single Scotiabank deposits that were multiple client payments")
print("   - These were identified and corrected in Neon")
print("   - Local may still have the incorrect single-payment records")
print("   - These should NOT be synced back to Neon")

print()

# ============================================================================
# STEP 6: CREATE DELETION CANDIDATE LIST
# ============================================================================
print("="*80)
print("STEP 6: DELETION CANDIDATE SUMMARY")
print("="*80)

deletion_candidates = set()

# Add duplicates (keep first, delete rest)
for group in cleanup_report['duplicate_groups']:
    deletion_candidates.update(group['delete_others'])

# Add QB contamination
for item in qb_contamination:
    deletion_candidates.update(item['payment_ids'])

# Add Square doubling (keep first of each group)
for item in square_doubling:
    # Keep first, delete rest
    if len(item['payment_ids']) > 1:
        deletion_candidates.update(item['payment_ids'][1:])

print(f"📋 DELETION CANDIDATE SUMMARY:")
print(f"   From deduplication:     {total_duplicates_to_delete:>8,} payments")
print(f"   From QB contamination:  {sum(item['contaminated_count'] for item in qb_contamination):>8,} payments")
print(f"   From Square doubling:   {sum(len(item['payment_ids']) - 1 for item in square_doubling):>8,} payments")
print(f"   {'-'*50}")
print(f"   TOTAL TO DELETE:        {len(deletion_candidates):>8,} payments")

cleanup_report['deletion_candidates'] = sorted(list(deletion_candidates))

# Calculate what remains
remaining_local_only = len(local_only_ids) - len(deletion_candidates)
print(f"\n📊 AFTER CLEANUP:")
print(f"   Protected (in Neon):    {len(protected_ids):>8,} payments")
print(f"   Remaining local-only:   {remaining_local_only:>8,} payments")
print(f"   {'-'*50}")
print(f"   TOTAL in local:         {len(protected_ids) + remaining_local_only:>8,} payments")

print()

# ============================================================================
# STEP 7: ASSESS REMAINING UNMATCHED
# ============================================================================
print("="*80)
print("STEP 7: ASSESS REMAINING UNMATCHED PAYMENTS")
print("="*80)

remaining_payment_ids = local_only_ids - deletion_candidates

if len(remaining_payment_ids) > 0:
    print(f"Analyzing {len(remaining_payment_ids):,} remaining unmatched payments...")
    
    local_cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date, payment_method
        FROM payments
        WHERE payment_id = ANY(%s)
    """, (sorted(list(remaining_payment_ids)),))
    
    remaining = local_cur.fetchall()
    
    # Check if these reserves exist in Neon but have NO payments
    reserves_no_neon_payments = set()
    for p in remaining:
        if p['reserve_number'] and p['reserve_number'] not in reserves_with_neon_payments:
            reserves_no_neon_payments.add(p['reserve_number'])
    
    print(f"\n✅ {len(reserves_no_neon_payments):,} reserves have NO payments in Neon yet")
    print(f"   → These {sum(1 for p in remaining if p['reserve_number'] in reserves_no_neon_payments):,} payments MAY be safe to sync")
    
    # Check for reserves that don't exist at all
    if reserves_no_neon_payments:
        neon_cur.execute("""
            SELECT reserve_number
            FROM charters
            WHERE reserve_number = ANY(%s)
        """, (list(reserves_no_neon_payments),))
        existing_reserves = set(row['reserve_number'] for row in neon_cur.fetchall())
        
        orphan_reserves = reserves_no_neon_payments - existing_reserves
        if orphan_reserves:
            print(f"\n⚠️  {len(orphan_reserves):,} reserves don't exist in Neon at all")
            print(f"   → Payments for these are ORPHANED - needs investigation")

print()

# ============================================================================
# SAVE CLEANUP REPORT
# ============================================================================
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
report_file = f"payment_cleanup_plan_{timestamp}.json"

with open(report_file, 'w') as f:
    json.dump(cleanup_report, f, indent=2, default=str)

print("="*80)
print(f"📄 Cleanup plan saved: {report_file}")
print("="*80)

# Create deletion SQL script
sql_file = f"delete_duplicate_payments_{timestamp}.sql"
with open(sql_file, 'w') as f:
    f.write("-- DELETE DUPLICATE PAYMENTS FROM LOCAL\n")
    f.write(f"-- Generated: {datetime.now()}\n")
    f.write(f"-- Total payments to delete: {len(deletion_candidates):,}\n\n")
    
    f.write("BEGIN;\n\n")
    
    f.write("-- Protected payment_ids (exist in Neon - DO NOT DELETE):\n")
    f.write(f"-- Count: {len(protected_ids):,}\n")
    f.write(f"-- These are safe in both databases\n\n")
    
    f.write("-- DELETION CANDIDATES:\n")
    f.write(f"DELETE FROM payments\nWHERE payment_id IN (\n")
    
    # Write in batches of 100
    id_batches = [list(deletion_candidates)[i:i+100] for i in range(0, len(deletion_candidates), 100)]
    for i, batch in enumerate(id_batches):
        ids_str = ', '.join(map(str, batch))
        f.write(f"  {ids_str}")
        if i < len(id_batches) - 1:
            f.write(",\n")
        else:
            f.write("\n")
    
    f.write(");\n\n")
    f.write("-- Verify count before committing:\n")
    f.write(f"-- Expected: {len(deletion_candidates):,} rows deleted\n\n")
    f.write("-- COMMIT;  -- Uncomment to commit\n")
    f.write("ROLLBACK;  -- Remove this line when ready to commit\n")

print(f"📄 Deletion SQL saved: {sql_file}")
print()

print("="*80)
print("NEXT STEPS:")
print("="*80)
print("1. Review the cleanup plan JSON file")
print("2. Verify deletion candidates make sense")
print("3. Run the SQL script (test with ROLLBACK first)")
print("4. Re-run forensic audit to verify cleanup")
print("5. Assess remaining payments for sync to Neon")
print()

local_conn.close()
neon_conn.close()

print("✅ Cleanup analysis complete")
