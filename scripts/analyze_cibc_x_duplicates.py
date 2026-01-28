#!/usr/bin/env python3
"""
Check if CIBC 'X' suffix entries are duplicates like Scotia 2012 closing entries.
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*80)
print('ANALYZING CIBC X ENTRIES FOR DUPLICATES')
print('='*80)
print()

# Get the 38 entries we just cleaned (now without X suffix)
print('Step 1: Get the 38 cleaned entries')
print('-'*80)

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        account_number
    FROM banking_transactions
    WHERE transaction_id IN (
        60414, 60400, 60381, 60333, 60324, 60297, 60302, 
        60300, 60283, 60288, 60396, 60334, 60922, 60415,
        60404, 60341, 60309, 60291, 60280, 60274, 60268,
        60262, 60256, 60250, 60244, 60238, 60232, 60226,
        60220, 60214, 60208, 60202, 60196, 60190, 60184,
        60178, 60172, 60166
    )
    ORDER BY transaction_date DESC, transaction_id
""")

x_entries = cur.fetchall()
print(f'Found {len(x_entries)} entries that had X suffix')
print()

# For each X entry, look for potential duplicates nearby
print('Step 2: Check for duplicate transactions (same date, amount, similar description)')
print('-'*80)

duplicates_found = []

for tid, date, desc, debit, credit, account in x_entries:
    # Look for transactions within ±3 days with same amount
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount
        FROM banking_transactions
        WHERE transaction_id != %s
        AND account_number = %s
        AND transaction_date BETWEEN %s::date - INTERVAL '3 days' 
                                 AND %s::date + INTERVAL '3 days'
        AND (
            (debit_amount = %s AND debit_amount IS NOT NULL)
            OR (credit_amount = %s AND credit_amount IS NOT NULL)
        )
        ORDER BY transaction_date, transaction_id
    """, (tid, account, date, date, debit, credit))
    
    matches = cur.fetchall()
    
    if matches:
        duplicates_found.append({
            'x_entry': (tid, date, desc, debit, credit),
            'matches': matches
        })

print(f'Found {len(duplicates_found)} X entries with potential duplicates')
print()

if duplicates_found:
    print('Step 3: Show duplicate groups')
    print('-'*80)
    
    for i, dup_group in enumerate(duplicates_found[:10], 1):  # Show first 10
        x_tid, x_date, x_desc, x_debit, x_credit = dup_group['x_entry']
        print(f'\nGroup {i}:')
        print(f'  X Entry: {x_tid} | {x_date} | {x_desc[:60]}')
        print(f'           Debit: ${x_debit or 0:.2f} | Credit: ${x_credit or 0:.2f}')
        
        for match_tid, match_date, match_desc, match_debit, match_credit in dup_group['matches']:
            print(f'  Match:   {match_tid} | {match_date} | {match_desc[:60]}')
            print(f'           Debit: ${match_debit or 0:.2f} | Credit: ${match_credit or 0:.2f}')
    
    if len(duplicates_found) > 10:
        print(f'\n... and {len(duplicates_found) - 10} more duplicate groups')

# Check if X entries are specifically cheque duplicates
print()
print('Step 4: Check if X entries duplicate cheques without X suffix')
print('-'*80)

cur.execute("""
    WITH x_cheques AS (
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount
        FROM banking_transactions
        WHERE transaction_id IN (
            60414, 60400, 60381, 60333, 60324, 60297, 60302, 
            60300, 60283, 60288, 60396, 60334, 60922, 60415,
            60404, 60341, 60309, 60291, 60280, 60274, 60268,
            60262, 60256, 60250, 60244, 60238, 60232, 60226,
            60220, 60214, 60208, 60202, 60196, 60190, 60184,
            60178, 60172, 60166
        )
        AND description LIKE 'Cheque%'
    )
    SELECT 
        x.transaction_id as x_tid,
        x.transaction_date as x_date,
        x.description as x_desc,
        x.debit_amount as x_debit,
        b.transaction_id as other_tid,
        b.transaction_date as other_date,
        b.description as other_desc,
        b.debit_amount as other_debit
    FROM x_cheques x
    JOIN banking_transactions b ON (
        b.transaction_id != x.transaction_id
        AND b.account_number = '0228362'
        AND b.transaction_date = x.transaction_date
        AND b.debit_amount = x.debit_amount
        AND b.description LIKE 'Cheque%'
    )
    ORDER BY x.transaction_date DESC
""")

cheque_dupes = cur.fetchall()
print(f'Found {len(cheque_dupes)} cheque X entries that duplicate other cheques')

if cheque_dupes:
    print('\nCheque duplicate examples:')
    for x_tid, x_date, x_desc, x_debit, other_tid, other_date, other_desc, other_debit in cheque_dupes[:10]:
        print(f'\nX Entry:  {x_tid} | {x_date} | {x_desc[:50]} | ${x_debit:.2f}')
        print(f'Duplicate: {other_tid} | {other_date} | {other_desc[:50]} | ${other_debit:.2f}')

# Summary recommendation
print()
print('='*80)
print('RECOMMENDATION')
print('='*80)

if len(duplicates_found) > 15 or len(cheque_dupes) > 10:
    print('⚠️  YES - These X entries appear to be duplicates and should be deleted')
    print(f'   {len(duplicates_found)} entries have matching transactions nearby')
    print(f'   {len(cheque_dupes)} cheque entries duplicate other cheques exactly')
    print()
    print('Next step: Run delete_cibc_x_duplicates.py to remove them')
else:
    print('✅ NO - These X entries do not appear to be systematic duplicates')
    print('   They may be legitimate transactions that just had X suffix artifacts')
    print('   The cleanup we did (removing X suffix) was correct')

cur.close()
conn.close()
