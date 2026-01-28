#!/usr/bin/env python3
"""
Find and delete QuickBooks entries from banking_transactions table.
Banking should only contain bank statement data, not QB entries.
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*80)
print('FINDING QUICKBOOKS ENTRIES IN BANKING_TRANSACTIONS')
print('='*80)
print()

print('Step 1: Count QuickBooks entries')
print('-'*80)

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions 
    WHERE description LIKE '%[QB:%' OR description LIKE '%QB:%'
""")
qb_count = cur.fetchone()[0]
print(f'Total QuickBooks entries: {qb_count}')

cur.execute("""
    SELECT account_number, COUNT(*) 
    FROM banking_transactions 
    WHERE description LIKE '%[QB:%' OR description LIKE '%QB:%'
    GROUP BY account_number
    ORDER BY account_number
""")
print('\nBy account:')
for acc, cnt in cur.fetchall():
    print(f'  {acc}: {cnt} entries')

print()
print('Step 2: Show sample QuickBooks entries')
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
    WHERE description LIKE '%[QB:%' OR description LIKE '%QB:%'
    ORDER BY transaction_date DESC 
    LIMIT 25
""")

qb_entries = cur.fetchall()
print(f'Sample of {len(qb_entries)} QuickBooks entries:')
for tid, date, desc, debit, credit, acc in qb_entries:
    print(f'{tid} | {acc} | {date} | D:${debit or 0:.2f} C:${credit or 0:.2f} | {desc[:60]}')

print()
print('Step 3: Create backup and delete')
print('-'*80)

# Create backup
backup_name = f'banking_transactions_qb_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
cur.execute(f"""
    CREATE TABLE {backup_name} AS
    SELECT * FROM banking_transactions
    WHERE description LIKE '%[QB:%' OR description LIKE '%QB:%'
""")

cur.execute(f"SELECT COUNT(*) FROM {backup_name}")
backup_count = cur.fetchone()[0]
print(f'✅ Backed up {backup_count} QuickBooks entries to {backup_name}')

# Delete QuickBooks entries
cur.execute("""
    DELETE FROM banking_transactions
    WHERE description LIKE '%[QB:%' OR description LIKE '%QB:%'
""")

deleted_count = cur.rowcount
print(f'✅ Deleted {deleted_count} QuickBooks entries from banking_transactions')

print()
print('Step 4: Verify clean state')
print('-'*80)

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions 
    WHERE description LIKE '%[QB:%' OR description LIKE '%QB:%'
""")
remaining = cur.fetchone()[0]
print(f'Remaining QuickBooks entries: {remaining}')

cur.execute("""
    SELECT account_number, COUNT(*) as tx_count
    FROM banking_transactions
    GROUP BY account_number
    ORDER BY account_number
""")

print('\nUpdated account summary:')
for acc, cnt in cur.fetchall():
    print(f'  {acc}: {cnt} transactions (bank statements only)')

print()
conn.commit()
print('✅ All changes committed')
print(f'✅ Backup available: {backup_name}')

cur.close()
conn.close()
