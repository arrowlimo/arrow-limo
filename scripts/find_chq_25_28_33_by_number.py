#!/usr/bin/env python3
"""Search banking records for CHQ 25, 26, 27, 28, 33 by cheque number AND by exact dollar amounts"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print('=' * 100)
print('SEARCHING BANKING FOR CHQ 25, 26, 27, 28, 33 BY CHEQUE NUMBER')
print('=' * 100)

# First: search by CHQ number mentions
cheques_to_find = [
    (25, 1475.25),
    (26, 1475.25),
    (27, 1475.25),
    (28, 1475.25),
    (33, 2525.25),
]

for chq_num, amount in cheques_to_find:
    print(f'\n\nSearching for CHQ {chq_num}...')
    print('-' * 100)
    
    # Search for "CHQ 25" or "CHQ 26" etc in description
    cur.execute("""
        SELECT transaction_id, transaction_date, description
        FROM banking_transactions
        WHERE description ILIKE %s
        ORDER BY transaction_date
    """, (f'%CHQ {chq_num}%',))
    
    matches = cur.fetchall()
    
    if matches:
        print(f'✓ FOUND {len(matches)} match(es) for "CHQ {chq_num}":')
        for tx_id, tx_date, desc in matches:
            print(f'  TX {tx_id} ({tx_date}): {desc}')
    else:
        print(f'✗ No "CHQ {chq_num}" found in banking')
        
        # Now search by exact dollar amount
        print(f'  Searching by exact amount ${amount:.2f}...')
        cur.execute("""
            SELECT transaction_id, transaction_date, description
            FROM banking_transactions
            WHERE description ILIKE %s
              AND transaction_date >= '2012-09-01'
              AND transaction_date <= '2014-01-31'
            ORDER BY transaction_date
        """, (f'%{amount}%',))
        
        amount_matches = cur.fetchall()
        
        if amount_matches:
            print(f'  Found {len(amount_matches)} transaction(s) with amount ${amount:.2f}:')
            for tx_id, tx_date, desc in amount_matches[:15]:  # Show first 15
                print(f'    TX {tx_id} ({tx_date}): {desc[:80]}')
        else:
            print(f'  ✗ No transactions found for ${amount:.2f}')

print('\n\n' + '=' * 100)
print('SUMMARY - ALL CHQ MENTIONS IN BANKING:')
print('=' * 100)

# Find all CHQ mentions in banking for Scotia dates (Sept 2012 - Jan 2014)
cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE description ~ 'CHQ [0-9]+'
      AND transaction_date >= '2012-09-01'
      AND transaction_date <= '2014-01-31'
    ORDER BY transaction_date
""")

all_chq_refs = cur.fetchall()

# Extract CHQ numbers from descriptions
chq_mentions = {}
for tx_id, tx_date, desc in all_chq_refs:
    # Look for "CHQ XXX" pattern
    import re
    matches = re.findall(r'CHQ\s+(\d+)', desc)
    for match in matches:
        chq_num = int(match)
        if chq_num not in chq_mentions:
            chq_mentions[chq_num] = []
        chq_mentions[chq_num].append((tx_id, tx_date, desc))

# Show all CHQ mentions
print(f'\nFound {len(chq_mentions)} unique CHQ numbers mentioned in banking:')
print('-' * 100)

for chq_num in sorted(chq_mentions.keys()):
    entries = chq_mentions[chq_num]
    print(f'\nCHQ {chq_num:3d}: {len(entries)} transaction(s)')
    for tx_id, tx_date, desc in entries:
        print(f'  TX {tx_id} ({tx_date}): {desc[:80]}')

# Show specifically what we're looking for
print('\n\n' + '=' * 100)
print('LOOKING FOR CHQ: 25, 26, 27, 28, 33')
print('=' * 100)

for chq_num in [25, 26, 27, 28, 33]:
    if chq_num in chq_mentions:
        print(f'\n✓ CHQ {chq_num} FOUND IN BANKING:')
        for tx_id, tx_date, desc in chq_mentions[chq_num]:
            print(f'  TX {tx_id} ({tx_date}): {desc}')
    else:
        print(f'\n✗ CHQ {chq_num} NOT mentioned in banking descriptions')

cur.close()
conn.close()
