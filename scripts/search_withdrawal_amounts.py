import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

amounts = [2695.40, 889.87, 471.98, 54.01, 788.22, 419.35, 20.00]
print('Searching for withdrawal amounts from PDF balance forward section:')
print('='*80)

for amt in amounts:
    # Search in debits (withdrawals)
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND debit_amount = %s
        AND transaction_date BETWEEN '2012-12-28' AND '2013-01-05'
        ORDER BY transaction_date
        LIMIT 5
    """, (amt,))
    
    matches = cur.fetchall()
    if matches:
        print(f'\n${amt}: Found {len(matches)} matches in Dec 28 - Jan 5 range')
        for row in matches:
            print(f'  {row[1]} | {row[2][:60] if row[2] else "N/A"} | Debit:{row[3]}')
    else:
        # Check if it exists anywhere
        cur.execute("""
            SELECT transaction_id, transaction_date, description
            FROM banking_transactions
            WHERE account_number = '903990106011'
            AND debit_amount = %s
            ORDER BY transaction_date
            LIMIT 2
        """, (amt,))
        
        any_matches = cur.fetchall()
        if any_matches:
            print(f'\n${amt}: Found elsewhere: {any_matches[0][1]} | {any_matches[0][2][:50]}')
        else:
            print(f'\n${amt}: NOT FOUND anywhere in Scotia account')

print('\n' + '='*80)
print('\nChecking account 1010 (QuickBooks import) for these amounts:')
print('-'*80)

for amt in amounts:
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE account_number = '1010'
        AND debit_amount = %s
        ORDER BY transaction_date
        LIMIT 2
    """, (amt,))
    
    matches = cur.fetchall()
    if matches:
        print(f'\n${amt}: Found in account 1010')
        for row in matches:
            desc = row[2] if row[2] else "(empty description)"
            print(f'  {row[1]} | {desc}')

cur.close()
conn.close()
