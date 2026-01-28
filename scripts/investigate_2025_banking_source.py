import psycopg2
import os
from collections import Counter

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print('=== BANKING TRANSACTIONS WITH 2025 DATES ===')
print('\n1. When were these created?')
cur.execute("""
    SELECT 
        DATE(created_at) as creation_date,
        COUNT(*) as count,
        MIN(transaction_date) as min_txn_date,
        MAX(transaction_date) as max_txn_date
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2025
    GROUP BY DATE(created_at)
    ORDER BY creation_date DESC
    LIMIT 20
""")
print(f'{"Creation Date":12} | {"Count":>5} | {"Transaction Date Range"}')
print('-' * 60)
for row in cur.fetchall():
    print(f'{row[0]} | {row[1]:>5} | {row[2]} to {row[3]}')

print('\n2. Account distribution:')
cur.execute("""
    SELECT 
        account_number,
        COUNT(*) as count,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2025
    GROUP BY account_number
    ORDER BY count DESC
""")
print(f'{"Account":15} | {"Count":>5} | {"Total Debits":>15} | {"Total Credits":>15}')
print('-' * 65)
for row in cur.fetchall():
    acct = row[0] if row[0] else 'NULL'
    debits = f'${row[2]:,.2f}' if row[2] else '$0.00'
    credits = f'${row[3]:,.2f}' if row[3] else '$0.00'
    print(f'{acct:15} | {row[1]:>5} | {debits:>15} | {credits:>15}')

print('\n3. Sample descriptions to identify pattern:')
cur.execute("""
    SELECT DISTINCT 
        LEFT(description, 60) as desc_pattern,
        COUNT(*) as occurrences
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2025
    GROUP BY LEFT(description, 60)
    ORDER BY occurrences DESC
    LIMIT 20
""")
print(f'{"Description Pattern":60} | {"Count":>5}')
print('-' * 70)
for row in cur.fetchall():
    print(f'{row[0]:60} | {row[1]:>5}')

# Check if these might actually be from 2012
print('\n4. Could these be 2012 transactions with wrong year?')
cur.execute("""
    SELECT 
        transaction_date,
        description,
        debit_amount,
        credit_amount
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2025
    ORDER BY transaction_date
    LIMIT 10
""")
print(f'\n{"Date":12} | {"Description":50} | {"Debit":>10} | {"Credit":>10}')
print('-' * 90)
for row in cur.fetchall():
    desc = (row[1][:50] if row[1] else 'N/A')
    debit = f'${row[2]:,.2f}' if row[2] else ''
    credit = f'${row[3]:,.2f}' if row[3] else ''
    print(f'{row[0]} | {desc:50} | {debit:>10} | {credit:>10}')

# Check if similar transactions exist in 2012
print('\n5. Checking for similar patterns in 2012:')
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    AND description LIKE '%REVENUE - Internet Banking%'
""")
count_2012 = cur.fetchone()[0]
print(f'   2012 transactions with "REVENUE - Internet Banking": {count_2012}')

cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2025
    AND description LIKE '%REVENUE - Internet Banking%'
""")
count_2025 = cur.fetchone()[0]
print(f'   2025 transactions with "REVENUE - Internet Banking": {count_2025}')

# Look at source_hash to see if there are duplicates
print('\n6. Checking for duplicate hashes (same transaction in multiple years):')
cur.execute("""
    WITH year_hashes AS (
        SELECT 
            source_hash,
            EXTRACT(YEAR FROM transaction_date) as year,
            COUNT(*) as count
        FROM banking_transactions
        WHERE source_hash IS NOT NULL
        AND EXTRACT(YEAR FROM transaction_date) IN (2012, 2025)
        GROUP BY source_hash, EXTRACT(YEAR FROM transaction_date)
    )
    SELECT 
        source_hash,
        STRING_AGG(year::TEXT || ' (' || count || ')', ', ') as years
    FROM year_hashes
    GROUP BY source_hash
    HAVING COUNT(DISTINCT year) > 1
    LIMIT 20
""")
duplicates = cur.fetchall()
if duplicates:
    print(f'   Found {len(duplicates)} duplicate transactions across years!')
    for row in duplicates[:10]:
        print(f'   Hash: {row[0][:16]}... appears in: {row[1]}')
else:
    print('   No duplicate hashes found between 2012 and 2025')

# Check the receipts linkage
print('\n7. How many 2025 receipts are linked to 2025 banking?')
cur.execute("""
    SELECT COUNT(DISTINCT r.receipt_id)
    FROM receipts r
    JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
    JOIN banking_transactions bt ON brml.banking_transaction_id = bt.transaction_id
    WHERE EXTRACT(YEAR FROM r.receipt_date) = 2025
    AND EXTRACT(YEAR FROM bt.transaction_date) = 2025
""")
linked = cur.fetchone()[0]
print(f'   {linked} receipts with 2025 dates are linked to 2025 banking transactions')

cur.close()
conn.close()

print('\n' + '='*70)
print('CONCLUSION:')
print('If these banking transactions were imported with wrong year,')
print('we need to fix both banking_transactions AND receipts tables.')
print('='*70)
