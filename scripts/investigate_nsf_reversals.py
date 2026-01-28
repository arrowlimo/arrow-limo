#!/usr/bin/env python3
"""
Investigate NSF reversal issue - find payment reversals that should pair with NSF charges.

Theory: When a payment bounces (NSF), the bank:
1. Charges an NSF fee (positive amount)
2. Reverses the original payment (negative amount)

We found 293 NSF charges but NO reversals. This script searches for
potential reversals that may have different vendor names or descriptions.
"""

import psycopg2
from datetime import datetime, timedelta

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print('='*80)
print('NSF REVERSAL INVESTIGATION - Finding Missing Payment Reversals')
print('='*80)
print()

# Step 1: Get all NSF charges in 2012
print('STEP 1: Collecting NSF Charge Data')
print('-'*80)

cur.execute('''
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        description
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    AND (
        vendor_name ILIKE '%NSF%'
        OR description ILIKE '%NSF%'
        OR description ILIKE '%NSF CHARGE%'
    )
    AND gross_amount > 0
    ORDER BY receipt_date
''')

nsf_charges = cur.fetchall()
print(f'Found {len(nsf_charges)} NSF charges (all positive)')
print()

# Step 2: Search for potential reversals (negative amounts)
print('STEP 2: Searching for Reversal Transactions (Negative Amounts)')
print('-'*80)

cur.execute('''
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        description
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    AND gross_amount < 0
    ORDER BY receipt_date, gross_amount
''')

negative_transactions = cur.fetchall()
print(f'Found {len(negative_transactions)} negative amount transactions')
print()

# Step 3: Look for reversal keywords
print('STEP 3: Searching for Reversal Keywords')
print('-'*80)

reversal_keywords = ['REVERSAL', 'CORRECTION', 'REVERSE', 'RETURN', 'CHARGEBACK', 
                    'CHARGE BACK', 'CANCELLED', 'BOUNCE', 'WITHDRAWN', 'CANCELLED']

cur.execute('''
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        description
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    AND (
        description ILIKE '%REVERSAL%'
        OR description ILIKE '%CORRECTION%'
        OR description ILIKE '%RETURN%'
        OR description ILIKE '%CHARGEBACK%'
        OR description ILIKE '%CHARGE BACK%'
        OR description ILIKE '%WITHDRAWN%'
        OR description ILIKE '%CANCELLED%'
        OR description ILIKE '%BOUNCE%'
    )
    ORDER BY receipt_date
''')

reversal_keywords_found = cur.fetchall()
print(f'Found {len(reversal_keywords_found)} transactions with reversal keywords')
print()

if reversal_keywords_found:
    print('Sample Reversal Keyword Transactions:')
    print('-'*80)
    for rec in reversal_keywords_found[:10]:
        rec_id, date, vendor, amount, desc = rec
        print(f'{date} | ${amount:>10,.2f} | {vendor[:30]}')
    print()

# Step 4: Look for "Customer Payment" entries (may be reversals)
print('STEP 4: Analyzing Customer Payment Entries')
print('-'*80)

cur.execute('''
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        description,
        COUNT(*) OVER (PARTITION BY receipt_date, gross_amount ORDER BY receipt_id) as dup_count
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    AND (vendor_name LIKE '%Customer Payment%' OR vendor_name LIKE '%NSF Event%')
    ORDER BY receipt_date, gross_amount
    LIMIT 50
''')

customer_payments = cur.fetchall()

if customer_payments:
    print(f'Found {len(customer_payments)} Customer Payment / NSF Event entries')
    print('These may be related transaction pairs:')
    print('-'*80)
    
    # Group by date and amount to find pairs
    from collections import defaultdict
    pairs = defaultdict(list)
    
    for rec in customer_payments:
        rec_id, date, vendor, amount, desc, dup_count = rec
        key = (date, amount)
        pairs[key].append((vendor, rec_id))
    
    for (date, amount), vendors in sorted(pairs.items()):
        if len(vendors) > 1:
            print(f'{date} | ${amount:>10,.2f} | {len(vendors)} entries:')
            for vendor, rec_id in vendors:
                print(f'  - {vendor}')
else:
    print('No explicit customer payment pairs found')

print()

# Step 5: Analysis and recommendations
print('ANALYSIS AND FINDINGS')
print('='*80)
print()

print('Possible NSF Reversal Scenarios:')
print('-'*80)
print()

print('Scenario 1: Original Payment NOT Reversed')
print('  Pattern: NSF charge exists, but original payment remains in database')
print('  Effect: Doubles the balance impact (charge counted, payment also counted)')
print('  Solution: Find and reverse original payment entry')
print()

print('Scenario 2: Reversals Exist But Not Marked as NSF')
print('  Pattern: Negative entries exist but use different vendor names')
print('  Effect: Reversals not associated with NSF charges')
print('  Solution: Search by matching date + mirror amounts')
print()

print('Scenario 3: NSF Data Entry Error')
print('  Pattern: NSF charges recorded but reversal process not completed')
print('  Effect: Banking balance incorrect by amount of NSF charge')
print('  Solution: Manual reconciliation with bank statements')
print()

# Step 6: Summary
print('='*80)
print('SUMMARY')
print('='*80)
print()
print(f'NSF Charges (Positive): {len(nsf_charges)}')
print(f'Negative Transactions: {len(negative_transactions)}')
print(f'Reversal Keywords Found: {len(reversal_keywords_found)}')
print(f'Customer Payment Pairs: {len(customer_payments)}')
print()

print('NEXT INVESTIGATION STEPS:')
print('-'*80)
print('1. Run: scripts/find_nsf_payment_pairs.py')
print('   (matches NSF charges with negative amounts by date/amount)')
print()
print('2. Compare 2012 database balances with bank statements')
print('   (verify if NSF-only or NSF+reversal issue)')
print()
print('3. Review original import source (LMS, QuickBooks, banking CSV)')
print('   (determine if reversals were included or omitted)')
print()

cur.close()
conn.close()

print('='*80)
