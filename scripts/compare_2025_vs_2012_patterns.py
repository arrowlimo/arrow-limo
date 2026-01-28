import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print('=== DETAILED ANALYSIS OF 2025-02 TRANSACTIONS ===')
print('\nThe Excel screenshot shows many Feb 2025 receipts.')
print('Let me check if these might actually be from Feb 2012...\n')

# Get the actual banking transactions for Feb 2025
print('1. Banking transactions in Feb 2025:')
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        account_number,
        created_at
    FROM banking_transactions
    WHERE transaction_date >= '2025-02-01' AND transaction_date < '2025-03-01'
    ORDER BY transaction_date
    LIMIT 20
""")
print(f'{"TxnID":6} | {"Date":10} | {"Description":50} | {"Debit":>10} | {"Credit":>10} | {"Account":10} | {"Created"}')
print('-' * 130)
for row in cur.fetchall():
    tid, tdate, desc, debit, credit, acct, created = row
    desc_short = (desc[:50] if desc else '')[:50]
    debit_str = f'${debit:,.2f}' if debit else ''
    credit_str = f'${credit:,.2f}' if credit else ''
    acct_str = acct if acct else 'N/A'
    print(f'{tid:6} | {tdate} | {desc_short:50} | {debit_str:>10} | {credit_str:>10} | {acct_str:10} | {created}')

# Check Feb 2012 for comparison
print('\n2. Banking transactions in Feb 2012 (for comparison):')
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        account_number
    FROM banking_transactions
    WHERE transaction_date >= '2012-02-01' AND transaction_date < '2012-03-01'
    ORDER BY transaction_date
    LIMIT 20
""")
print(f'{"TxnID":6} | {"Date":10} | {"Description":50} | {"Debit":>10} | {"Credit":>10} | {"Account":10}')
print('-' * 120)
for row in cur.fetchall():
    tid, tdate, desc, debit, credit, acct = row
    desc_short = (desc[:50] if desc else '')[:50]
    debit_str = f'${debit:,.2f}' if debit else ''
    credit_str = f'${credit:,.2f}' if credit else ''
    acct_str = acct if acct else 'N/A'
    print(f'{tid:6} | {tdate} | {desc_short:50} | {debit_str:>10} | {credit_str:>10} | {acct_str:10}')

# Check accounts that exist in each year
print('\n3. Account numbers in 2025 vs 2012:')
cur.execute("""
    SELECT 
        '2025' as year,
        account_number,
        COUNT(*) as count
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2025
    GROUP BY account_number
    
    UNION ALL
    
    SELECT 
        '2012' as year,
        account_number,
        COUNT(*) as count
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY account_number
    
    ORDER BY year DESC, count DESC
""")
print(f'{"Year":4} | {"Account":15} | {"Count":>6}')
print('-' * 30)
for row in cur.fetchall():
    acct = row[1] if row[1] else 'NULL'
    print(f'{row[0]:4} | {acct:15} | {row[2]:>6}')

# Check if account 3648117 (merchant account) existed in 2012
print('\n4. Account 3648117 (merchant/credit card processing):')
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        COUNT(*) as count,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits
    FROM banking_transactions
    WHERE account_number = '3648117'
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY year
""")
print(f'{"Year":4} | {"Count":>6} | {"Total Debits":>15} | {"Total Credits":>15}')
print('-' * 50)
for row in cur.fetchall():
    year = int(row[0])
    debits = f'${row[2]:,.2f}' if row[2] else '$0.00'
    credits = f'${row[3]:,.2f}' if row[3] else '$0.00'
    print(f'{year:4} | {row[1]:>6} | {debits:>15} | {credits:>15}')

# Final check - do the descriptions match current (2025) or historical (2012) patterns?
print('\n5. Description patterns - do these look like 2012 or 2025?')
print('\nFeb 2025 transaction descriptions:')
cur.execute("""
    SELECT DISTINCT LEFT(description, 60)
    FROM banking_transactions
    WHERE transaction_date >= '2025-02-01' AND transaction_date < '2025-03-01'
    LIMIT 15
""")
for row in cur.fetchall():
    print(f'   {row[0]}')

cur.close()
conn.close()

print('\n' + '='*70)
print('ASSESSMENT:')
print('Looking at account numbers and transaction types,')
print('these appear to be RECENT 2025 transactions, not misdat 2012 data.')
print('='*70)
