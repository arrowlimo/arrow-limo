#!/usr/bin/env python3
"""
Fix the 3 remaining blank descriptions:
- Delete 62890 (duplicate)
- Set description for 62623 and 62775 as "Unknown Transaction"
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*80)
print('FIXING REMAINING 3 BLANK DESCRIPTIONS')
print('='*80)
print()

print('Step 1: Create backup of 3 entries')
print('-'*80)

backup_name = f'banking_transactions_blank_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
cur.execute(f"""
    CREATE TABLE {backup_name} AS
    SELECT * FROM banking_transactions
    WHERE transaction_id IN (62623, 62775, 62890)
""")
print(f'✅ Backed up to {backup_name}')

print()
print('Step 2: Delete duplicate entry 62890')
print('-'*80)

cur.execute("""
    SELECT transaction_id, transaction_date, debit_amount
    FROM banking_transactions
    WHERE transaction_id = 62890
""")
dup_info = cur.fetchone()
print(f'Deleting: {dup_info[0]} | {dup_info[1]} | ${dup_info[2]:.2f}')

# Check for foreign keys first
cur.execute("""
    SELECT COUNT(*) FROM receipts WHERE banking_transaction_id = 62890
""")
receipt_refs = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*) FROM banking_receipt_matching_ledger WHERE banking_transaction_id = 62890
""")
ledger_refs = cur.fetchone()[0]

if receipt_refs > 0:
    cur.execute("UPDATE receipts SET banking_transaction_id = NULL WHERE banking_transaction_id = 62890")
    print(f'  Cleared {cur.rowcount} receipt references')

if ledger_refs > 0:
    cur.execute("DELETE FROM banking_receipt_matching_ledger WHERE banking_transaction_id = 62890")
    print(f'  Deleted {cur.rowcount} ledger references')

cur.execute("DELETE FROM banking_transactions WHERE transaction_id = 62890")
print(f'✅ Deleted duplicate transaction 62890')

print()
print('Step 3: Set descriptions for legitimate blank entries')
print('-'*80)

cur.execute("""
    UPDATE banking_transactions
    SET description = 'Unknown Transaction'
    WHERE transaction_id IN (62623, 62775)
""")
print(f'✅ Updated {cur.rowcount} descriptions to "Unknown Transaction"')

print()
print('Step 4: Verify no more blanks')
print('-'*80)

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions
    WHERE description IS NULL OR TRIM(description) = ''
""")
remaining = cur.fetchone()[0]
print(f'Remaining blank descriptions: {remaining}')

cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE transaction_id IN (62623, 62775)
    ORDER BY transaction_date
""")

print('\nFixed entries:')
for tid, date, desc, debit, credit in cur.fetchall():
    print(f'{tid} | {date} | {desc} | ${debit or 0:.2f}/${credit or 0:.2f}')

print()
conn.commit()
print('✅ All changes committed')
print(f'✅ Backup: {backup_name}')

cur.close()
conn.close()
