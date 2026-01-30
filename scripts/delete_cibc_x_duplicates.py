#!/usr/bin/env python3
"""
Delete CIBC X duplicate entries (same pattern as Scotia 2012 closing entries).
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*80)
print('DELETING CIBC X DUPLICATE ENTRIES')
print('='*80)
print()

# Create backup first
backup_name = f'banking_transactions_cibc_x_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
print(f'Step 1: Creating backup table: {backup_name}')
print('-'*80)

cur.execute(f"""
    CREATE TABLE {backup_name} AS
    SELECT * FROM banking_transactions
    WHERE transaction_id IN (
        60414, 60400, 60381, 60333, 60324, 60297, 60302, 
        60300, 60283, 60288, 60396, 60334, 60922, 60415,
        60404, 60341, 60309, 60291, 60280, 60274, 60268,
        60262, 60256, 60250, 60244, 60238, 60232, 60226,
        60220, 60214, 60208, 60202, 60196, 60190, 60184,
        60178, 60172, 60166
    )
""")

cur.execute(f"SELECT COUNT(*) FROM {backup_name}")
backup_count = cur.fetchone()[0]
print(f'✅ Backed up {backup_count} X entries to {backup_name}')

print()
print('Step 2: Verify these are duplicates')
print('-'*80)

# Show some examples of what we're deleting
cur.execute("""
    SELECT 
        x.transaction_id,
        x.transaction_date,
        x.description,
        x.debit_amount,
        COUNT(DISTINCT b.transaction_id) as duplicate_count
    FROM banking_transactions x
    JOIN banking_transactions b ON (
        b.transaction_id != x.transaction_id
        AND b.account_number = x.account_number
        AND b.transaction_date = x.transaction_date
        AND COALESCE(b.debit_amount, 0) = COALESCE(x.debit_amount, 0)
        AND COALESCE(b.credit_amount, 0) = COALESCE(x.credit_amount, 0)
    )
    WHERE x.transaction_id IN (
        60414, 60400, 60381, 60333, 60324, 60297, 60302, 
        60300, 60283, 60288, 60396, 60334, 60922, 60415,
        60404, 60341, 60309, 60291, 60280, 60274, 60268,
        60262, 60256, 60250, 60244, 60238, 60232, 60226,
        60220, 60214, 60208, 60202, 60196, 60190, 60184,
        60178, 60172, 60166
    )
    GROUP BY x.transaction_id, x.transaction_date, x.description, x.debit_amount
    HAVING COUNT(DISTINCT b.transaction_id) > 0
    ORDER BY x.transaction_date DESC
    LIMIT 10
""")

examples = cur.fetchall()
print(f'Found {len(examples)} verified duplicates (showing up to 10):')
for tid, date, desc, amount, dup_count in examples:
    print(f'  {tid} | {date} | ${amount:.2f} | {desc[:50]} | {dup_count} other copies')

print()
print('Step 3: Delete X duplicate entries')
print('-'*80)

cur.execute("""
    DELETE FROM banking_transactions
    WHERE transaction_id IN (
        60414, 60400, 60381, 60333, 60324, 60297, 60302, 
        60300, 60283, 60288, 60396, 60334, 60922, 60415,
        60404, 60341, 60309, 60291, 60280, 60274, 60268,
        60262, 60256, 60250, 60244, 60238, 60232, 60226,
        60220, 60214, 60208, 60202, 60196, 60190, 60184,
        60178, 60172, 60166
    )
""")

deleted_count = cur.rowcount
print(f'✅ Deleted {deleted_count} X duplicate entries')

print()
print('Step 4: Verify CIBC account summary')
print('-'*80)

cur.execute("""
    SELECT 
        account_number,
        COUNT(*) as transaction_count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits
    FROM banking_transactions
    WHERE account_number = '0228362'
    GROUP BY account_number
""")

account, count, first, last, debits, credits = cur.fetchone()
print(f'CIBC Account {account}:')
print(f'  Transactions: {count}')
print(f'  Date range: {first} to {last}')
print(f'  Total debits: ${debits:,.2f}')
print(f'  Total credits: ${credits:,.2f}')

print()
conn.commit()
print('✅ All changes committed')
print(f'✅ Backup available in table: {backup_name}')

cur.close()
conn.close()
