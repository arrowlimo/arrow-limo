#!/usr/bin/env python3
"""
CHARTER RECONCILIATION ANALYSIS
================================

Compare charter balance vs payments in Neon to identify:
1. Fully reconciled charters (do not sync local payments)
2. Partially paid charters (local payments may be legitimate)
3. 2025+ charters still being paid (Square/cash/cheque)
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, date
from collections import defaultdict
import json

from dotenv import load_dotenv
load_dotenv()

print("="*80)
print("CHARTER RECONCILIATION - NEON BALANCE ANALYSIS")
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

# ============================================================================
# STEP 1: Get charter balances and payment totals from Neon
# ============================================================================
print("\n" + "="*80)
print("STEP 1: ANALYZE NEON CHARTER BALANCES")
print("="*80)

neon_cur = neon_conn.cursor()

print("Loading Neon charter data with payment reconciliation...")
neon_cur.execute("""
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.charter_date,
        c.total_amount_due,
        c.paid_amount,
        c.payment_status,
        COALESCE(SUM(p.amount), 0) as total_payments,
        COUNT(p.payment_id) as payment_count,
        c.total_amount_due - COALESCE(SUM(p.amount), 0) as calculated_balance
    FROM charters c
    LEFT JOIN payments p ON p.charter_id = c.charter_id
    GROUP BY c.charter_id, c.reserve_number, c.charter_date, 
             c.total_amount_due, c.paid_amount, c.payment_status
    ORDER BY c.charter_date DESC, c.reserve_number
""")

neon_charters = neon_cur.fetchall()
print(f"✅ Loaded {len(neon_charters):,} charters from Neon\n")

# Categorize charters
fully_paid = []
partially_paid = []
not_paid = []
overpaid = []

for charter in neon_charters:
    calculated_bal = charter['calculated_balance']
    
    if calculated_bal is None or charter['total_amount_due'] is None:
        continue
    
    if abs(calculated_bal) < 0.01:  # Fully paid (within 1 cent)
        fully_paid.append(charter)
    elif calculated_bal < -0.01:  # Overpaid
        overpaid.append(charter)
    elif charter['total_payments'] == 0:  # No payments
        not_paid.append(charter)
    else:  # Partially paid
        partially_paid.append(charter)

print("📊 NEON CHARTER STATUS:")
print(f"   ✅ Fully Paid:      {len(fully_paid):>8,} charters (DO NOT SYNC local payments)")
print(f"   💰 Partially Paid:  {len(partially_paid):>8,} charters (MAY need local payments)")
print(f"   ⚠️  Not Paid:        {len(not_paid):>8,} charters (MAY need local payments)")
print(f"   🔴 Overpaid:        {len(overpaid):>8,} charters (investigate)")

# ============================================================================
# STEP 2: Get local-only payments
# ============================================================================
print("\n" + "="*80)
print("STEP 2: ANALYZE LOCAL-ONLY PAYMENTS")
print("="*80)

local_cur = local_conn.cursor()

# Get Neon payment IDs to identify local-only
neon_cur.execute("SELECT payment_id FROM payments")
neon_payment_ids = set(row['payment_id'] for row in neon_cur.fetchall())

# Get all local payments
local_cur.execute("""
    SELECT payment_id, reserve_number, amount, payment_date, 
           payment_method, created_at
    FROM payments
    ORDER BY payment_id
""")
all_local = local_cur.fetchall()

local_only_payments = [p for p in all_local if p['payment_id'] not in neon_payment_ids]

print(f"✅ Found {len(local_only_payments):,} local-only payments")

# Group by reserve_number
by_reserve = defaultdict(list)
for p in local_only_payments:
    if p['reserve_number']:
        by_reserve[p['reserve_number']].append(p)

print(f"   {len(by_reserve):,} unique reserve numbers\n")

# ============================================================================
# STEP 3: Match local payments to charter status
# ============================================================================
print("="*80)
print("STEP 3: MATCH LOCAL PAYMENTS TO CHARTER STATUS")
print("="*80)

# Create charter lookup
charter_lookup = {c['reserve_number']: c for c in neon_charters}

# Categorize local payments by charter status
payments_for_fully_paid = []  # DO NOT SYNC
payments_for_partially_paid = []  # MAY SYNC
payments_for_not_paid = []  # LIKELY SYNC
payments_for_2025_plus = []  # 2025+ being paid
payments_no_charter = []  # Orphaned

cutoff_date = date(2025, 1, 1)

for reserve_num, payments in by_reserve.items():
    charter = charter_lookup.get(reserve_num)
    
    if not charter:
        payments_no_charter.extend(payments)
        continue
    
    charter_date = charter['charter_date']
    is_2025_plus = charter_date >= cutoff_date if charter_date else False
    
    calculated_bal = charter['calculated_balance']
    
    # Fully paid charters - DO NOT SYNC
    if calculated_bal is not None and abs(calculated_bal) < 0.01:
        for p in payments:
            payments_for_fully_paid.append({
                'payment': p,
                'charter': charter,
                'reason': 'Charter fully reconciled in Neon',
                'action': 'DELETE from local'
            })
    
    # 2025+ charters - likely legitimate Square/cash/cheque
    elif is_2025_plus:
        for p in payments:
            payments_for_2025_plus.append({
                'payment': p,
                'charter': charter,
                'reason': '2025+ charter - may still be collecting payment',
                'action': 'REVIEW - may be legitimate'
            })
    
    # Partially paid
    elif charter['total_payments'] > 0:
        for p in payments:
            payments_for_partially_paid.append({
                'payment': p,
                'charter': charter,
                'reason': 'Charter partially paid - additional payment possible',
                'action': 'REVIEW'
            })
    
    # Not paid at all
    elif charter['total_payments'] == 0:
        for p in payments:
            payments_for_not_paid.append({
                'payment': p,
                'charter': charter,
                'reason': 'No payments in Neon - likely needs sync',
                'action': 'SYNC to Neon'
            })

print("\n📋 LOCAL PAYMENT CLASSIFICATION:")
print(f"   🔴 For FULLY PAID charters:    {len(payments_for_fully_paid):>8,} payments → DELETE")
print(f"   ✅ For NOT PAID charters:      {len(payments_for_not_paid):>8,} payments → SYNC")
print(f"   💰 For PARTIALLY PAID:         {len(payments_for_partially_paid):>8,} payments → REVIEW")
print(f"   📅 For 2025+ charters:         {len(payments_for_2025_plus):>8,} payments → REVIEW")
print(f"   ❓ No charter found:           {len(payments_no_charter):>8,} payments → ORPHANED")

# ============================================================================
# STEP 4: Analyze payments for fully paid charters
# ============================================================================
print("\n" + "="*80)
print("STEP 4: PAYMENTS FOR FULLY PAID CHARTERS (DELETE CANDIDATES)")
print("="*80)

if payments_for_fully_paid:
    print(f"\n✅ {len(payments_for_fully_paid):,} payments for charters already fully paid in Neon")
    print("\n   Sample (first 20):")
    print(f"   {'Reserve':>8} {'Charter Date':>12} {'Amount':>12} {'Payment Method':>15} {'Neon Balance':>12}")
    print(f"   {'-'*70}")
    
    for item in payments_for_fully_paid[:20]:
        p = item['payment']
        c = item['charter']
        print(f"   {p['reserve_number']:>8} {str(c['charter_date'] or 'N/A'):>12} "
              f"${p['amount'] or 0:>10,.2f} {p['payment_method'] or 'unknown':>15} "
              f"${c['calculated_balance'] or 0:>10,.2f}")
    
    if len(payments_for_fully_paid) > 20:
        print(f"   ... and {len(payments_for_fully_paid) - 20} more")

# ============================================================================
# STEP 5: Analyze 2025+ payments
# ============================================================================
print("\n" + "="*80)
print("STEP 5: 2025+ CHARTER PAYMENTS (STILL BEING PAID)")
print("="*80)

if payments_for_2025_plus:
    print(f"\n📅 {len(payments_for_2025_plus):,} payments for 2025+ charters")
    
    # Group by payment method
    by_method = defaultdict(list)
    for item in payments_for_2025_plus:
        method = item['payment']['payment_method'] or 'unknown'
        by_method[method].append(item)
    
    print("\n   By payment method:")
    for method, items in sorted(by_method.items(), key=lambda x: -len(x[1])):
        total = sum(item['payment']['amount'] or 0 for item in items)
        print(f"   - {method:20} {len(items):>6,} payments (${total:>12,.2f})")
    
    print("\n   Sample (first 10):")
    print(f"   {'Reserve':>8} {'Charter Date':>12} {'Amount':>12} {'Method':>15} {'Neon Paid':>12} {'Balance':>12}")
    print(f"   {'-'*80}")
    
    for item in payments_for_2025_plus[:10]:
        p = item['payment']
        c = item['charter']
        print(f"   {p['reserve_number']:>8} {str(c['charter_date']):>12} "
              f"${p['amount'] or 0:>10,.2f} {p['payment_method'] or 'unknown':>15} "
              f"${c['total_payments'] or 0:>10,.2f} ${c['calculated_balance'] or 0:>10,.2f}")

# ============================================================================
# STEP 6: Create deletion list
# ============================================================================
print("\n" + "="*80)
print("STEP 6: DELETION RECOMMENDATION")
print("="*80)

delete_ids = [item['payment']['payment_id'] for item in payments_for_fully_paid]

print(f"\n🔴 RECOMMENDED FOR DELETION:")
print(f"   {len(delete_ids):,} payments for charters that are fully reconciled in Neon")
print(f"   These are duplicates - charter balance is already $0.00")

# ============================================================================
# STEP 7: Sync recommendation
# ============================================================================
print("\n" + "="*80)
print("STEP 7: SYNC RECOMMENDATION")
print("="*80)

sync_ids = [item['payment']['payment_id'] for item in payments_for_not_paid]

print(f"\n✅ RECOMMENDED FOR SYNC TO NEON:")
print(f"   {len(sync_ids):,} payments for charters with NO payments in Neon")
print(f"   These charters need payment data")

review_ids = [item['payment']['payment_id'] for item in (payments_for_partially_paid + payments_for_2025_plus)]

print(f"\n⚠️  NEEDS MANUAL REVIEW:")
print(f"   {len(review_ids):,} payments for partially paid or 2025+ charters")
print(f"   May be legitimate Square/cash/cheque payments")

# ============================================================================
# Save analysis
# ============================================================================
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
report_file = f"charter_reconciliation_analysis_{timestamp}.json"

report = {
    'timestamp': datetime.now().isoformat(),
    'neon_charters': {
        'fully_paid': len(fully_paid),
        'partially_paid': len(partially_paid),
        'not_paid': len(not_paid),
        'overpaid': len(overpaid)
    },
    'local_payments': {
        'for_fully_paid_charters': len(payments_for_fully_paid),
        'for_not_paid_charters': len(payments_for_not_paid),
        'for_partially_paid_charters': len(payments_for_partially_paid),
        'for_2025_plus_charters': len(payments_for_2025_plus),
        'orphaned': len(payments_no_charter)
    },
    'recommendations': {
        'delete_payment_ids': delete_ids,
        'sync_to_neon_payment_ids': sync_ids,
        'needs_review_payment_ids': review_ids
    },
    'details': {
        'fully_paid_charters': [
            {
                'reserve_number': item['charter']['reserve_number'],
                'charter_date': str(item['charter']['charter_date']) if item['charter']['charter_date'] else None,
                'total_due': float(item['charter']['total_amount_due']) if item['charter']['total_amount_due'] else None,
                'neon_payments': float(item['charter']['total_payments']),
                'balance': float(item['charter']['calculated_balance']),
                'local_payment_id': item['payment']['payment_id'],
                'local_amount': float(item['payment']['amount'] or 0),
                'action': 'DELETE'
            }
            for item in payments_for_fully_paid
        ],
        'not_paid_charters': [
            {
                'reserve_number': item['charter']['reserve_number'],
                'charter_date': str(item['charter']['charter_date']) if item['charter']['charter_date'] else None,
                'total_due': float(item['charter']['total_amount_due']) if item['charter']['total_amount_due'] else None,
                'local_payment_id': item['payment']['payment_id'],
                'local_amount': float(item['payment']['amount'] or 0),
                'action': 'SYNC'
            }
            for item in payments_for_not_paid
        ]
    }
}

with open(report_file, 'w') as f:
    json.dump(report, f, indent=2, default=str)

print(f"\n📄 Analysis saved: {report_file}")

# Create deletion SQL
if delete_ids:
    sql_file = f"delete_fully_paid_charter_payments_{timestamp}.sql"
    with open(sql_file, 'w') as f:
        f.write("-- DELETE PAYMENTS FOR FULLY RECONCILED CHARTERS\n")
        f.write(f"-- These charters have balance = $0.00 in Neon\n")
        f.write(f"-- Count: {len(delete_ids):,}\n\n")
        f.write("BEGIN;\n\n")
        f.write("DELETE FROM payments WHERE payment_id IN (\n")
        
        batch_size = 100
        batches = [delete_ids[i:i+batch_size] for i in range(0, len(delete_ids), batch_size)]
        for i, batch in enumerate(batches):
            f.write(f"  {', '.join(map(str, batch))}")
            if i < len(batches) - 1:
                f.write(",\n")
            else:
                f.write("\n")
        
        f.write(");\n\n")
        f.write(f"-- Expected: {len(delete_ids):,} rows deleted\n\n")
        f.write("COMMIT;\n")
    
    print(f"📄 Deletion SQL saved: {sql_file}")

local_conn.close()
neon_conn.close()

print("\n✅ Charter reconciliation analysis complete")
