#!/usr/bin/env python3
"""
FORENSIC AUDIT: PAYMENTS TABLE
===============================

Compare local almsdata.payments vs Neon neondb.payments
- Neon has 20,416 rows (confirmed LMS-synced data)
- Local has 28,907 rows (8,491 more)
- Investigate: duplicates, corruption, Square update issues

Goal: Identify safe records to sync vs corrupted duplicates
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from collections import defaultdict
import json

from dotenv import load_dotenv
load_dotenv()

# Connect to both databases
print("Connecting to databases...")
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

print("✅ Connected to both databases\n")

audit_report = {
    "timestamp": datetime.now().isoformat(),
    "neon_count": 0,
    "local_count": 0,
    "difference": 0,
    "exact_matches": 0,
    "local_only": 0,
    "neon_only": 0,
    "duplicate_payments": [],
    "charter_analysis": {},
    "potential_corruption": [],
    "safe_to_sync": [],
    "recommendations": []
}

# ============================================================================
# STEP 1: Get basic counts
# ============================================================================
print("="*80)
print("STEP 1: BASIC ROW COUNTS")
print("="*80)

local_cur = local_conn.cursor()
local_cur.execute("SELECT COUNT(*) as count FROM payments")
local_count = local_cur.fetchone()['count']
audit_report['local_count'] = local_count

neon_cur = neon_conn.cursor()
neon_cur.execute("SELECT COUNT(*) as count FROM payments")
neon_count = neon_cur.fetchone()['count']
audit_report['neon_count'] = neon_count

difference = local_count - neon_count
audit_report['difference'] = difference

print(f"Neon (confirmed LMS data):  {neon_count:>8,} rows")
print(f"Local (almsdata):           {local_count:>8,} rows")
print(f"Difference:                 {difference:>8,} rows")
print()

# ============================================================================
# STEP 2: Get payment_id ranges
# ============================================================================
print("="*80)
print("STEP 2: PAYMENT_ID RANGES")
print("="*80)

local_cur.execute("SELECT MIN(payment_id) as min_id, MAX(payment_id) as max_id FROM payments")
local_range = local_cur.fetchone()
print(f"Local:  payment_id {local_range['min_id']:>6} to {local_range['max_id']:>6}")

neon_cur.execute("SELECT MIN(payment_id) as min_id, MAX(payment_id) as max_id FROM payments")
neon_range = neon_cur.fetchone()
print(f"Neon:   payment_id {neon_range['min_id']:>6} to {neon_range['max_id']:>6}")
print()

# ============================================================================
# STEP 3: Get all payment_ids from both databases
# ============================================================================
print("="*80)
print("STEP 3: COMPARING PAYMENT_IDS")
print("="*80)

print("Loading Neon payment_ids...")
neon_cur.execute("SELECT payment_id FROM payments ORDER BY payment_id")
neon_ids = set(row['payment_id'] for row in neon_cur.fetchall())
print(f"   Loaded {len(neon_ids):,} payment_ids from Neon")

print("Loading Local payment_ids...")
local_cur.execute("SELECT payment_id FROM payments ORDER BY payment_id")
local_ids = set(row['payment_id'] for row in local_cur.fetchall())
print(f"   Loaded {len(local_ids):,} payment_ids from Local")

# Find differences
ids_in_both = neon_ids & local_ids
ids_only_local = local_ids - neon_ids
ids_only_neon = neon_ids - local_ids

audit_report['exact_matches'] = len(ids_in_both)
audit_report['local_only'] = len(ids_only_local)
audit_report['neon_only'] = len(ids_only_neon)

print(f"\n✅ In BOTH databases:      {len(ids_in_both):>8,} payment_ids")
print(f"📤 ONLY in Local:          {len(ids_only_local):>8,} payment_ids")
print(f"📥 ONLY in Neon:           {len(ids_only_neon):>8,} payment_ids")
print()

# ============================================================================
# STEP 4: Analyze payments that exist in BOTH
# ============================================================================
print("="*80)
print("STEP 4: ANALYZING PAYMENTS IN BOTH DATABASES")
print("="*80)
print("Checking for data differences in shared payment_ids...")

if len(ids_in_both) > 0:
    # Sample first 100 to check for differences
    sample_ids = sorted(list(ids_in_both))[:100]
    
    local_cur.execute("""
        SELECT payment_id, reserve_number, amount, 
               payment_date, payment_method, created_at
        FROM payments
        WHERE payment_id = ANY(%s)
        ORDER BY payment_id
    """, (sample_ids,))
    local_sample = {row['payment_id']: row for row in local_cur.fetchall()}
    
    neon_cur.execute("""
        SELECT payment_id, reserve_number, charter_id, amount, 
               payment_date, payment_method, created_at
        FROM payments
        WHERE payment_id = ANY(%s)
        ORDER BY payment_id
    """, (sample_ids,))
    neon_sample = {row['payment_id']: row for row in neon_cur.fetchall()}
    
    differences_found = 0
    for pid in sample_ids:
        local_rec = local_sample.get(pid)
        neon_rec = neon_sample.get(pid)
        
        if local_rec and neon_rec:
            # Compare key fields (note: local doesn't have charter_id)
            if (local_rec['amount'] != neon_rec['amount'] or
                local_rec['reserve_number'] != neon_rec['reserve_number']):
                differences_found += 1
                print(f"   ⚠️  payment_id {pid}: Data differs between local and Neon")
    
    if differences_found == 0:
        print(f"   ✅ Sample of {len(sample_ids)} records: All data matches")
    else:
        print(f"   ⚠️  Found {differences_found} records with different data")
print()

# ============================================================================
# STEP 5: Analyze LOCAL-ONLY payments
# ============================================================================
print("="*80)
print("STEP 5: ANALYZING LOCAL-ONLY PAYMENTS (8,491 records)")
print("="*80)

if len(ids_only_local) > 0:
    print(f"Analyzing {len(ids_only_local):,} payments that exist ONLY in local...")
    
    local_cur.execute("""
        SELECT 
            payment_id,
            reserve_number,
            amount,
            payment_date,
            payment_method,
            created_at,
            notes
        FROM payments
        WHERE payment_id = ANY(%s)
        ORDER BY payment_id
    """, (sorted(list(ids_only_local)),))
    
    local_only_payments = local_cur.fetchall()
    
    # Group by reserve_number (since local doesn't have charter_id)
    by_reserve = defaultdict(list)
    no_reserve = []
    
    for payment in local_only_payments:
        if payment['reserve_number']:
            by_reserve[payment['reserve_number']].append(payment)
        else:
            no_reserve.append(payment)
    
    print(f"\n   Grouped by reserve_number:")
    print(f"   - With reserve_number:    {sum(len(v) for v in by_reserve.values()):>8,} payments")
    print(f"   - Without reserve_number: {len(no_reserve):>8,} payments")
    print(f"   - Unique reserves:        {len(by_reserve):>8,} reserve numbers")
    
    # Check payment methods
    method_counts = defaultdict(int)
    for payment in local_only_payments:
        method = payment['payment_method'] or 'NULL'
        method_counts[method] += 1
    
    print(f"\n   Payment methods breakdown:")
    for method, count in sorted(method_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"   - {method:20} {count:>8,} payments")
    
    # Check date ranges
    dates = [p['payment_date'] for p in local_only_payments if p['payment_date']]
    if dates:
        print(f"\n   Date range:")
        print(f"   - Earliest: {min(dates)}")
        print(f"   - Latest:   {max(dates)}")
    
    # Look for potential duplicates by amount + date
    print(f"\n   Checking for potential duplicates...")
    dup_key_counts = defaultdict(list)
    for payment in local_only_payments:
        key = (payment['reserve_number'], payment['amount'], payment['payment_date'])
        dup_key_counts[key].append(payment['payment_id'])
    
    duplicates = {k: v for k, v in dup_key_counts.items() if len(v) > 1}
    if duplicates:
        print(f"   ⚠️  Found {len(duplicates)} potential duplicate groups:")
        # Sort by number of duplicates, not by the key (which has None values)
        sorted_dups = sorted(duplicates.items(), key=lambda x: -len(x[1]))
        for (reserve, amount, date), pids in sorted_dups[:5]:
            print(f"      Reserve {reserve}, ${amount}, {date}: {len(pids)} payments (IDs: {pids})")
        if len(duplicates) > 5:
            print(f"      ... and {len(duplicates) - 5} more duplicate groups")
        
        audit_report['duplicate_payments'] = [
            {
                'reserve_number': k[0],
                'amount': float(k[1]) if k[1] else None,
                'payment_date': str(k[2]) if k[2] else None,
                'payment_ids': v,
                'count': len(v)
            }
            for k, v in duplicates.items()
        ]
    else:
        print(f"   ✅ No obvious duplicates found (by reserve + amount + date)")

print()

# ============================================================================
# STEP 6: Check if local-only payments reference charters in Neon
# ============================================================================
print("="*80)
print("STEP 6: CHARTER CROSS-REFERENCE ANALYSIS")
print("="*80)

if len(ids_only_local) > 0:
    print("Checking if local-only payments reference charters that exist in Neon...")
    print("(Local doesn't have charter_id, so matching by reserve_number)")
    
    # Get reserve_numbers from local-only payments
    reserve_numbers = [rn for rn in by_reserve.keys() if rn]
    
    if reserve_numbers:
        # Check which reserves exist in Neon
        neon_cur.execute("""
            SELECT charter_id, reserve_number, charter_date, total_amount_due
            FROM charters
            WHERE reserve_number = ANY(%s)
        """, (reserve_numbers,))
        neon_charters = {row['reserve_number']: row for row in neon_cur.fetchall()}
        
        print(f"\n   Reserves referenced by local-only payments:")
        print(f"   - Total referenced:       {len(reserve_numbers):>8,}")
        print(f"   - Exist in Neon:          {len(neon_charters):>8,}")
        print(f"   - NOT in Neon:            {len(reserve_numbers) - len(neon_charters):>8,}")
        
        # For charters that exist in Neon, check if Neon already has payments
        if neon_charters:
            print(f"\n   Checking if Neon already has payments for these charters...")
            
            charter_ids = [c['charter_id'] for c in neon_charters.values()]
            neon_cur.execute("""
                SELECT charter_id, COUNT(*) as payment_count, SUM(amount) as total_paid
                FROM payments
                WHERE charter_id = ANY(%s)
                GROUP BY charter_id
            """, (charter_ids,))
            neon_charter_payments_by_id = {row['charter_id']: row for row in neon_cur.fetchall()}
            
            # Map back to reserve_number
            potential_corruption = []
            for reserve_num in by_reserve.keys():
                if reserve_num not in neon_charters:
                    continue
                    
                neon_charter = neon_charters[reserve_num]
                charter_id = neon_charter['charter_id']
                local_payments = by_reserve[reserve_num]
                neon_payments = neon_charter_payments_by_id.get(charter_id)
                
                if neon_payments:
                    # Charter has payments in BOTH databases - potential duplication
                    local_total = sum(p['amount'] or 0 for p in local_payments)
                    neon_total = neon_payments['total_paid'] or 0
                    
                    potential_corruption.append({
                        'reserve_number': reserve_num,
                        'charter_id': charter_id,
                        'charter_total_due': float(neon_charter['total_amount_due']) if neon_charter['total_amount_due'] else None,
                        'neon_payments': neon_payments['payment_count'],
                        'neon_total': float(neon_total),
                        'local_only_payments': len(local_payments),
                        'local_only_total': float(local_total),
                        'status': 'POTENTIAL_DUPLICATE' if abs(local_total - neon_total) < 0.01 else 'DIFFERENT_AMOUNTS'
                    })
            
            if potential_corruption:
                print(f"\n   ⚠️  POTENTIAL CORRUPTION/DUPLICATES: {len(potential_corruption)} charters")
                print(f"\n   These charters have payments in BOTH Neon AND local-only:")
                print(f"   {'Reserve':>8} {'Charter':>10} {'Neon Pmts':>10} {'Local-Only':>12} {'Status':>20}")
                print(f"   {'-'*70}")
                
                for item in sorted(potential_corruption, key=lambda x: -x['local_only_payments'])[:20]:
                    print(f"   {item['reserve_number']:>8} {item['charter_id']:>10} "
                          f"{item['neon_payments']:>10} {item['local_only_payments']:>12} "
                          f"{item['status']:>20}")
                
                if len(potential_corruption) > 20:
                    print(f"   ... and {len(potential_corruption) - 20} more")
                
                audit_report['potential_corruption'] = potential_corruption
            else:
                print(f"   ✅ No charters with duplicate payments detected")

print()

# ============================================================================
# STEP 7: Recommendations
# ============================================================================
print("="*80)
print("STEP 7: RECOMMENDATIONS")
print("="*80)

recommendations = []

if len(ids_only_neon) > 0:
    recommendations.append(f"⚠️  {len(ids_only_neon):,} payments exist in Neon but NOT in local - local may be missing data")

if len(duplicates) > 0:
    recommendations.append(f"🔴 {len(duplicates)} duplicate groups found in local-only payments - likely corruption from Square update")
    recommendations.append(f"   → Review duplicate_payments in audit report")
    recommendations.append(f"   → These should NOT be synced to Neon")

if len(potential_corruption) > 0:
    recommendations.append(f"🔴 {len(potential_corruption)} charters have payments in BOTH Neon and local-only")
    recommendations.append(f"   → These are likely duplicates from Square sync corruption")
    recommendations.append(f"   → DO NOT sync these - they would create duplicate payments")

safe_to_sync_count = len(ids_only_local) - sum(len(v) for v in duplicates.values()) - sum(p['local_only_payments'] for p in potential_corruption)
if safe_to_sync_count > 0:
    recommendations.append(f"✅ Approximately {safe_to_sync_count:,} local-only payments MAY be safe to sync")
    recommendations.append(f"   → Requires manual review of remaining records")
else:
    recommendations.append(f"⚠️  No obviously safe records identified for sync")

recommendations.append(f"\nNEXT STEPS:")
recommendations.append(f"1. Review audit report: forensic_audit_payments_YYYYMMDD.json")
recommendations.append(f"2. Manually inspect duplicate groups")
recommendations.append(f"3. Verify charters with duplicate payments")
recommendations.append(f"4. Create cleanup script to remove corruption")
recommendations.append(f"5. Re-run audit after cleanup")

for rec in recommendations:
    print(f"   {rec}")

audit_report['recommendations'] = recommendations

print()

# ============================================================================
# Save audit report
# ============================================================================
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
report_file = f"forensic_audit_payments_{timestamp}.json"

with open(report_file, 'w') as f:
    json.dump(audit_report, f, indent=2, default=str)

print("="*80)
print(f"📄 Audit report saved: {report_file}")
print("="*80)

local_conn.close()
neon_conn.close()

print("\n✅ Forensic audit complete")
