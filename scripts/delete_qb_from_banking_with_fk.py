#!/usr/bin/env python3
"""
Delete QuickBooks entries from banking_transactions, handling foreign key constraints.
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*80)
print('REMOVING QUICKBOOKS ENTRIES FROM BANKING_TRANSACTIONS')
print('='*80)
print()

print('Step 1: Check foreign key constraints')
print('-'*80)

# Check cheque_register references
cur.execute("""
    SELECT COUNT(*)
    FROM cheque_register cr
    JOIN banking_transactions bt ON cr.banking_transaction_id = bt.transaction_id
    WHERE bt.description LIKE '%[QB:%' OR bt.description LIKE '%QB:%'
""")
cheque_refs = cur.fetchone()[0]
print(f'Cheque register references to QB entries: {cheque_refs}')

# Check banking_receipt_matching_ledger references
cur.execute("""
    SELECT COUNT(*)
    FROM banking_receipt_matching_ledger bm
    JOIN banking_transactions bt ON bm.banking_transaction_id = bt.transaction_id
    WHERE bt.description LIKE '%[QB:%' OR bt.description LIKE '%QB:%'
""")
receipt_refs = cur.fetchone()[0]
print(f'Receipt matching ledger references to QB entries: {receipt_refs}')

# Check receipts.banking_transaction_id references
cur.execute("""
    SELECT COUNT(*)
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.description LIKE '%[QB:%' OR bt.description LIKE '%QB:%'
""")
receipt_direct_refs = cur.fetchone()[0]
print(f'Receipts direct references to QB entries: {receipt_direct_refs}')

print()
print('Step 2: Create backup')
print('-'*80)

backup_name = f'banking_transactions_qb_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
cur.execute(f"""
    CREATE TABLE {backup_name} AS
    SELECT * FROM banking_transactions
    WHERE description LIKE '%[QB:%' OR description LIKE '%QB:%'
""")

cur.execute(f"SELECT COUNT(*) FROM {backup_name}")
backup_count = cur.fetchone()[0]
print(f'✅ Backed up {backup_count} QuickBooks entries to {backup_name}')

print()
print('Step 3: Remove foreign key references')
print('-'*80)

# Remove cheque_register references
if cheque_refs > 0:
    cur.execute("""
        UPDATE cheque_register
        SET banking_transaction_id = NULL
        WHERE banking_transaction_id IN (
            SELECT transaction_id FROM banking_transactions
            WHERE description LIKE '%[QB:%' OR description LIKE '%QB:%'
        )
    """)
    print(f'✅ Cleared {cur.rowcount} cheque_register references')

# Remove banking_receipt_matching_ledger references
if receipt_refs > 0:
    cur.execute("""
        DELETE FROM banking_receipt_matching_ledger
        WHERE banking_transaction_id IN (
            SELECT transaction_id FROM banking_transactions
            WHERE description LIKE '%[QB:%' OR description LIKE '%QB:%'
        )
    """)
    print(f'✅ Deleted {cur.rowcount} receipt matching links')

# Remove receipts.banking_transaction_id references
if receipt_direct_refs > 0:
    cur.execute("""
        UPDATE receipts
        SET banking_transaction_id = NULL
        WHERE banking_transaction_id IN (
            SELECT transaction_id FROM banking_transactions
            WHERE description LIKE '%[QB:%' OR description LIKE '%QB:%'
        )
    """)
    print(f'✅ Cleared {cur.rowcount} receipt direct references')

print()
print('Step 4: Delete QuickBooks entries')
print('-'*80)

cur.execute("""
    DELETE FROM banking_transactions
    WHERE description LIKE '%[QB:%' OR description LIKE '%QB:%'
""")

deleted_count = cur.rowcount
print(f'✅ Deleted {deleted_count} QuickBooks entries')

print()
print('Step 5: Verify clean state')
print('-'*80)

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions 
    WHERE description LIKE '%[QB:%' OR description LIKE '%QB:%'
""")
remaining = cur.fetchone()[0]
print(f'Remaining QuickBooks entries: {remaining}')

cur.execute("""
    SELECT account_number, COUNT(*) as tx_count,
           MIN(transaction_date) as first_date,
           MAX(transaction_date) as last_date
    FROM banking_transactions
    GROUP BY account_number
    ORDER BY account_number
""")

print('\nUpdated banking accounts (bank statements only):')
for acc, cnt, first, last in cur.fetchall():
    print(f'  {acc}: {cnt} transactions ({first} to {last})')

print()
conn.commit()
print('✅ All changes committed')
print(f'✅ Backup: {backup_name}')
print()
print('Summary: Banking transactions now contains ONLY bank statement data')

cur.close()
conn.close()
