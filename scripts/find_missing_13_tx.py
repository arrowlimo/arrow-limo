#!/usr/bin/env python3
"""Find 13 missing TX matches - identify why no banking link"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print('CHEQUES WITHOUT BANKING TX ID:')
print('=' * 80)

cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, status
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER BETWEEN 1 AND 117
      AND banking_transaction_id IS NULL
    ORDER BY cheque_number::INTEGER
""")

missing_cheques = cur.fetchall()

for num, date, payee, amount, status in missing_cheques:
    num_int = int(num)
    date_str = str(date) if date else 'NO DATE'
    print(f'CHQ {num_int:3d}: {payee:30s} | ${amount:10.2f} | {date_str} | {status}')

print(f'\nTotal missing TX IDs: {len(missing_cheques)}')

# Now search banking for these amounts
print('\n' + '=' * 80)
print('SEARCHING BANKING RECORDS FOR THESE AMOUNTS:')
print('=' * 80)

for num, date, payee, amount, status in missing_cheques:
    num_int = int(num)
    
    # Search for amount in banking
    cur.execute("""
        SELECT transaction_id, transaction_date, description
        FROM banking_transactions
        WHERE (description ILIKE %s OR description::text LIKE %s)
        ORDER BY transaction_date DESC
        LIMIT 3
    """, (f'%{amount}%', f'%{payee}%'))
    
    matches = cur.fetchall()
    
    if matches:
        print(f'\nCHQ {num_int}: {payee} ${amount}')
        for tx_id, tx_date, desc in matches:
            print(f'  → TX {tx_id} ({tx_date}): {desc[:60]}')
    else:
        print(f'\nCHQ {num_int}: {payee} ${amount} - NO BANKING MATCH FOUND')

cur.close()
conn.close()
