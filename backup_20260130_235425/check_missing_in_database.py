import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

conn = get_db_connection()
cur = conn.cursor()

amounts = [193.00, 594.98, 102.23, 165.00, 205.00]
print('Searching database for missing deposit amounts:', amounts)
print('='*80)

for amt in amounts:
    # Search in credits (deposits)
    cur.execute("""
        SELECT transaction_id, transaction_date, description, credit_amount, debit_amount, balance
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND (credit_amount = %s OR debit_amount = %s)
        AND transaction_date BETWEEN '2012-12-01' AND '2013-01-31'
        ORDER BY transaction_date
        LIMIT 5
    """, (amt, amt))
    
    matches = cur.fetchall()
    if matches:
        print(f'\n${amt}: Found {len(matches)} matches in database')
        for row in matches:
            print(f'  ID {row[0]}: {row[1]} | {row[2][:60] if row[2] else "N/A"} | Credit:{row[3]} Debit:{row[4]}')
    else:
        print(f'\n${amt}: NOT FOUND in database for Dec 2012 - Jan 2013')

print('\n' + '='*80)
print('\nChecking if these are balance-forward opening entries...')

# Check for transactions around Dec 1, 2012
cur.execute("""
    SELECT transaction_id, transaction_date, description, credit_amount, debit_amount, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND transaction_date BETWEEN '2012-11-28' AND '2012-12-05'
    ORDER BY transaction_date, transaction_id
    LIMIT 20
""")

print('\nTransactions around Dec 1-5, 2012:')
for row in cur.fetchall():
    print(f'  ID {row[0]}: {row[1]} | {row[2][:60] if row[2] else "N/A"} | Credit:{row[3]} Debit:{row[4]} Balance:{row[5]}')

cur.close()
conn.close()
