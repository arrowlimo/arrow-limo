#!/usr/bin/env python3
"""Link the 13 missing cheques to their banking TX records"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Manually identified matches based on banking search results
links_to_create = [
    # CHQ 25, 26, 27, 28 are HEFFNER AUTO $1475.25 - need to find specific dates
    # These appear to be duplicate entries - multiple same amounts
    # Can't safely link without dates to distinguish them
    
    # CHQ 87: JEANNIE SHILLINGTON $1500.00
    (87, 81039, '2012-09-01'),  # TX 81039 (2012-09-01): Cheque Expense - Jeannie Shillington
    
    # CHQ 92: TREDD MAYFAIR $613.00 - marked VOID
    # TX 81124 (2012-11-06): Cheque Expense - Tredd Mayfair Insurance Brokers Ltd. - VOID
    (92, 81124, '2012-11-06'),
    
    # CHQ 94: JACK CARTER $1885.65
    (94, 82296, '2012-09-17'),  # TX 82296 (2012-09-17): JACK CARTER
    
    # CHQ 117: MICHAEL RICHARD $841.11
    (117, 81114, '2012-11-04'),  # TX 81114 (2012-11-04): Cheque Expense - Michael Richard
]

print('LINKING 13 MISSING CHEQUES TO BANKING TX:')
print('=' * 100)

# For HEFFNER AUTO (25, 26, 27, 28, 33) - need to match with specific TX based on order
# These are all lease payments for different L-9 and L-10 units
# Without dates, can't safely match them to specific TX

# Let's find which HEFFNER auto TX exist for these amounts and dates
print('\nSearching for HEFFNER AUTO transactions to match CHQ 25, 26, 27, 28, 33...')
print('-' * 100)

cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE description ILIKE '%HEFFNER%'
      AND transaction_date >= '2012-09-01'
      AND transaction_date <= '2014-01-31'
    ORDER BY transaction_date
""")

heffner_txs = cur.fetchall()

# Group by amount
heffner_1475_25 = [t for t in heffner_txs if '1475.25' in t[2]]
heffner_2525_25 = [t for t in heffner_txs if '2525.25' in t[2]]

print(f'\nFound {len(heffner_1475_25)} HEFFNER AUTO transactions for $1475.25')
print(f'Found {len(heffner_2525_25)} HEFFNER AUTO transactions for $2525.25')

# Show first 10 of each
if heffner_1475_25:
    print('\nFirst HEFFNER AUTO $1475.25 transactions:')
    for i, (tx_id, tx_date, desc) in enumerate(heffner_1475_25[:10]):
        print(f'  {i+1}. TX {tx_id} ({tx_date}): {desc[:60]}')

if heffner_2525_25:
    print('\nFirst HEFFNER AUTO $2525.25 transactions:')
    for i, (tx_id, tx_date, desc) in enumerate(heffner_2525_25[:10]):
        print(f'  {i+1}. TX {tx_id} ({tx_date}): {desc[:60]}')

print('\n' + '=' * 100)
print('SAFE MATCHES TO APPLY:')
print('=' * 100)

# Apply safe matches
for chq_num, tx_id, chq_date in links_to_create:
    print(f'\nUpdating CHQ {chq_num}...')
    try:
        cur.execute("""
            UPDATE cheque_register
            SET banking_transaction_id = %s, cheque_date = %s, status = 'CLEARED'
            WHERE cheque_number = %s::TEXT
        """, (tx_id, chq_date, str(chq_num)))
        
        print(f'  ✓ CHQ {chq_num} → TX {tx_id} ({chq_date})')
    except Exception as e:
        print(f'  ✗ ERROR: {e}')

conn.commit()

print('\n' + '=' * 100)
print('⚠️  HEFFNER AUTO CHEQUES (25, 26, 27, 28, 33) - CANNOT LINK WITHOUT DATES')
print('=' * 100)
print('These cheques lack dates in the original register.')
print('Multiple $1475.25 and $2525.25 HEFFNER transactions exist.')
print('Cannot safely assign without original cheque dates.')
print('Recommend checking hand-written register for these cheque dates.')

print('\n' + '=' * 100)
print('STILL UNLINKED CHEQUES:')
print('=' * 100)

unlinked = [
    (10, 'NOT ISSUED', 0.00, 'VOID - correctly unlinked'),
    (25, 'HEFFNER AUTO', 1475.25, 'Need date from register'),
    (26, 'HEFFNER AUTO', 1475.25, 'Need date from register'),
    (27, 'HEFFNER AUTO', 1475.25, 'Need date from register'),
    (28, 'HEFFNER AUTO', 1475.25, 'Need date from register'),
    (33, 'HEFFNER AUTO', 2525.25, 'Need date from register'),
    (41, 'REVENUE CANADA', 3993.79, 'No banking match found'),
    (93, 'WORD OF LIFE', 200.00, 'Donation - VOID correctly unlinked'),
    (108, 'SHAWN CALLIN', 564.92, 'No banking match found'),
]

for chq_num, payee, amount, reason in unlinked:
    print(f'CHQ {chq_num:3d}: {payee:20s} ${amount:10.2f} - {reason}')

cur.close()
conn.close()

print('\n' + '=' * 100)
print('Next step: Check hand-written register for dates of CHQ 25, 26, 27, 28, 33')
print('=' * 100)
