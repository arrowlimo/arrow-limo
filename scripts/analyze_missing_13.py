#!/usr/bin/env python3
"""Identify and link the 13 missing cheques to correct banking TX"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# The 13 missing cheques - analyze each one
missing_cheques = [
    (10, 'NOT ISSUED', 0.00),
    (25, 'HEFFNER AUTO', 1475.25),
    (26, 'HEFFNER AUTO', 1475.25),
    (27, 'HEFFNER AUTO', 1475.25),
    (28, 'HEFFNER AUTO', 1475.25),
    (33, 'HEFFNER AUTO', 2525.25),
    (41, 'REVENUE CANADA', 3993.79),
    (87, 'JEANNIE SHILLINGTON', 1500.00),
    (92, 'TREDD MAYFAIR', 613.00),
    (93, 'WORD OF LIFE', 200.00),
    (94, 'JACK CARTER', 1885.65),
    (108, 'SHAWN CALLIN', 564.92),
    (117, 'MICHAEL RICHARD', 841.11),
]

print('ANALYSIS OF 13 MISSING CHEQUES:')
print('=' * 100)

updates_needed = []

for chq_num, payee, amount in missing_cheques:
    print(f'\nCHQ {chq_num}: {payee} ${amount:.2f}')
    print('-' * 100)
    
    # Search by amount + payee
    cur.execute("""
        SELECT transaction_id, transaction_date, description
        FROM banking_transactions
        WHERE description ILIKE %s
          AND transaction_date >= '2012-09-01'
          AND transaction_date <= '2014-01-31'
        ORDER BY transaction_date
    """, (f'%{payee.split()[0]}%',))
    
    matches = cur.fetchall()
    
    if not matches:
        print(f'  ⚠️  NO BANKING MATCHES FOUND')
    else:
        # Find best match
        best_match = None
        for tx_id, tx_date, desc in matches:
            # Check if amount appears in description
            if f'${amount:.2f}' in desc or f'{amount:.2f}' in desc:
                best_match = (tx_id, tx_date, desc)
                break
        
        if best_match:
            tx_id, tx_date, desc = best_match
            print(f'  ✓ FOUND: TX {tx_id} ({tx_date}): {desc[:70]}')
            updates_needed.append((chq_num, tx_id, tx_date))
        else:
            # Show all matches
            print(f'  Found {len(matches)} HEFFNER transactions:')
            for tx_id, tx_date, desc in matches[:5]:
                print(f'    - TX {tx_id} ({tx_date}): {desc[:60]}')

print('\n' + '=' * 100)
print('SUMMARY OF UPDATES NEEDED:')
print('=' * 100)

for chq_num, tx_id, tx_date in updates_needed:
    print(f'CHQ {chq_num:3d} → TX {tx_id} ({tx_date})')

cur.close()
conn.close()
