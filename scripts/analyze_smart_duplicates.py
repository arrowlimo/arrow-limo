#!/usr/bin/env python3
"""
Smart duplicate detection that understands recurring payments and NSF patterns.
- Monthly lease/rent payments: SAME amount, DIFFERENT dates = NOT duplicates
- Auto-withdrawal NSF: CHARGE without reversal = NOT duplicates (never actually withdrawn)
- True duplicates: SAME date, SAME amount, SAME vendor = DELETE
"""

import psycopg2
from datetime import datetime, timedelta
from collections import defaultdict

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print('='*80)
print('SMART DUPLICATE DETECTION - RESPECTING RECURRING PAYMENTS & NSF PATTERNS')
print('='*80)
print(f'Analysis Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print()

# RULE 1: Recurring payments (same amount, different dates) are NOT duplicates
# Examples: Monthly rent, monthly lease fees, regular subscriptions
RECURRING_KEYWORDS = ['RENT', 'LEASE', 'SUBSCRIPTION', 'MONTHLY', 'RECURRING', 
                      'MORTGAGE', 'INSURANCE', 'UTILITIES', 'PHONE', 'INTERNET']

# RULE 2: NSF-only charges (no reversal) are NOT duplicates
# Auto-withdrawal NSF = charge appears but money never actually left account

# RULE 3: TRUE duplicates - exact same date, amount, vendor
# These are import artifacts or data entry errors

print('RULE DEFINITIONS:')
print('-'*80)
print('Rule 1: Recurring Payments')
print('  Pattern: Same amount on different dates')
print('  Keywords: RENT, LEASE, SUBSCRIPTION, MONTHLY, INSURANCE, UTILITIES')
print('  Action: KEEP ALL (not duplicates)')
print()
print('Rule 2: Auto-Withdrawal NSF')
print('  Pattern: NSF charge with NO corresponding reversal')
print('  Amount: Charge appears but reversed in bank statement')
print('  Action: KEEP ALL (never actually withdrawn)')
print()
print('Rule 3: True Duplicates')
print('  Pattern: Exact SAME date + SAME amount + SAME vendor')
print('  Action: DELETE (keep first, remove rest)')
print()

# Step 1: Identify recurring payments
print('STEP 1: Identifying Recurring Payments (not duplicates)')
print('-'*80)

recurring_ids = set()

for keyword in RECURRING_KEYWORDS:
    cur.execute('''
        SELECT receipt_id
        FROM receipts
        WHERE (
            vendor_name ILIKE %s
            OR description ILIKE %s
        )
    ''', (f'%{keyword}%', f'%{keyword}%'))
    
    for row in cur.fetchall():
        recurring_ids.add(row[0])

print(f'Found {len(recurring_ids):,} recurring payment receipts')
print('These will NOT be considered duplicates')
print()

# Step 2: Identify NSF-only charges (no reversals)
print('STEP 2: Identifying Auto-Withdrawal NSF Charges (not duplicates)')
print('-'*80)

nsf_only_ids = set()

cur.execute('''
    SELECT DISTINCT r.receipt_id
    FROM receipts r
    WHERE (
        r.vendor_name LIKE '%NSF%'
        OR r.description LIKE '%NSF%'
    )
    AND r.gross_amount > 0
    AND NOT EXISTS (
        SELECT 1 FROM receipts r2
        WHERE r2.receipt_date = r.receipt_date
        AND r2.gross_amount = -r.gross_amount
        AND (r2.vendor_name LIKE '%Customer Payment%' OR r2.description LIKE '%Customer Payment%')
    )
''')

for row in cur.fetchall():
    nsf_only_ids.add(row[0])

print(f'Found {len(nsf_only_ids):,} NSF-only charges (no reversals)')
print('These will NOT be considered duplicates')
print()

# Step 3: Find TRUE duplicates (same date, amount, vendor)
print('STEP 3: Finding TRUE Duplicates (same date, amount, vendor)')
print('-'*80)

cur.execute('''
    SELECT 
        DATE(receipt_date) as receipt_date,
        gross_amount,
        vendor_name,
        COUNT(*) as count,
        ARRAY_AGG(receipt_id ORDER BY receipt_id) as ids
    FROM receipts
    WHERE NOT (
        vendor_name LIKE '%NSF%'
        OR vendor_name LIKE '%Customer Payment%'
        OR vendor_name LIKE '%NSF Event%'
        OR description LIKE '%NSF%'
        OR description LIKE '%NSF Event%'
    )
    GROUP BY DATE(receipt_date), gross_amount, vendor_name
    HAVING COUNT(*) > 1
    ORDER BY DATE(receipt_date) DESC, gross_amount DESC
''')

dup_groups = cur.fetchall()
total_true_dups = 0
delete_ids = set()

for date, amount, vendor, count, ids in dup_groups:
    # Skip if all IDs are in recurring or NSF-only sets
    ids_list = list(ids)
    recurring_count = sum(1 for id in ids_list if id in recurring_ids)
    nsf_only_count = sum(1 for id in ids_list if id in nsf_only_ids)
    
    # If ANY are recurring or NSF-only, KEEP ALL (don't delete)
    if recurring_count > 0 or nsf_only_count > 0:
        continue
    
    # TRUE duplicate group - keep first, mark rest for deletion
    keep_id = ids_list[0]
    for delete_id in ids_list[1:]:
        delete_ids.add(delete_id)
        total_true_dups += 1

print(f'Found {len(delete_ids):,} TRUE duplicate receipts to delete')
print(f'Across {len(dup_groups):,} duplicate groups')
print()

# Step 4: Breakdown by year
print('STEP 4: Duplicates by Year (respecting recurring & NSF)')
print('-'*80)

if delete_ids:
    cur.execute('''
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as dup_count,
            SUM(gross_amount) as dup_amount
        FROM receipts
        WHERE receipt_id = ANY(%s)
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year DESC
    ''', (list(delete_ids),))
    
    for year, count, amount in cur.fetchall():
        print(f'{int(year)}: {count:,} receipts | ${float(amount if amount else 0):,.2f}')

print()

# Step 5: Show sample duplicates
print('STEP 5: Sample TRUE Duplicates Found')
print('-'*80)

if delete_ids:
    cur.execute('''
        SELECT 
            DATE(receipt_date) as receipt_date,
            vendor_name,
            gross_amount,
            COUNT(*) as instances,
            ARRAY_AGG(receipt_id) as ids
        FROM receipts
        WHERE receipt_id = ANY(%s)
        GROUP BY DATE(receipt_date), vendor_name, gross_amount
        ORDER BY COUNT(*) DESC
        LIMIT 10
    ''', (list(delete_ids),))
    
    for date, vendor, amount, instances, ids in cur.fetchall():
        print(f'{date} | {vendor[:40]:40} | ${float(amount):>10,.2f} | {instances} copies')

print()

# Step 6: Recommendations
print('='*80)
print('SUMMARY AND RECOMMENDATIONS')
print('='*80)
print()
print(f'Recurring Payments (PROTECTED): {len(recurring_ids):,} receipts')
print(f'NSF-Only Charges (PROTECTED): {len(nsf_only_ids):,} receipts')
print(f'TRUE Duplicates to Delete: {len(delete_ids):,} receipts')
print()

if len(delete_ids) > 0:
    print('SAFE TO DELETE:')
    print('✅ All TRUE duplicates are exact matches (same date, amount, vendor)')
    print('✅ Recurring payments are protected')
    print('✅ NSF-only charges are protected')
    print()
    print('To execute deletion:')
    print('  python scripts/execute_smart_duplicate_cleanup.py')
else:
    print('No TRUE duplicates found!')
    print('All potential duplicates are recurring payments or NSF-only charges.')

print()

cur.close()
conn.close()
