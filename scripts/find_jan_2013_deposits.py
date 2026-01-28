import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

conn = get_db_connection()
cur = conn.cursor()

print('Searching for deposits around Jan 2, 2013 in Scotia account 903990106011')
print('='*80)

# Get all transactions from late Dec 2012 through early Jan 2013
cur.execute("""
    SELECT transaction_id, transaction_date, description, credit_amount, debit_amount, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND transaction_date BETWEEN '2012-12-28' AND '2013-01-10'
    ORDER BY transaction_date, transaction_id
""")

transactions = cur.fetchall()
print(f'\nFound {len(transactions)} transactions from Dec 28, 2012 to Jan 10, 2013:')
print('-'*80)

for row in transactions:
    tid, tdate, desc, credit, debit, balance = row
    if credit:
        amt_str = f"Credit:{credit:>8.2f}"
    elif debit:
        amt_str = f"Debit:{debit:>8.2f} "
    else:
        amt_str = "Amount:    0.00 "
    desc_short = (desc[:50] if desc else "N/A").ljust(50)
    bal_str = f"{balance:.2f}" if balance else "None"
    print(f"{tdate} | {desc_short} | {amt_str} | Bal:{bal_str}")

print('\n' + '='*80)
print('\nSearching specifically for the missing amounts:')
amounts = [193.00, 594.98, 102.35, 165.00, 205.00]  # Note: 102.35 not 102.23

for amt in amounts:
    cur.execute("""
        SELECT transaction_id, transaction_date, description, credit_amount, debit_amount
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND (credit_amount = %s OR debit_amount = %s)
        ORDER BY transaction_date
        LIMIT 3
    """, (amt, amt))
    
    matches = cur.fetchall()
    if matches:
        print(f'\n${amt}: Found {len(matches)} matches anywhere in Scotia history')
        for row in matches:
            print(f'  {row[1]} | {row[2][:50] if row[2] else "N/A"}')
    else:
        print(f'\n${amt}: NOT FOUND anywhere in Scotia account')

cur.close()
conn.close()
