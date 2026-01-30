#!/usr/bin/env python3
"""
Populate banking_transaction_id in receipts table from existing reconciliation data.
Links receipts back to the banking transactions they came from.
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*80)
print('POPULATING RECEIPTS.BANKING_TRANSACTION_ID FROM RECONCILIATION DATA')
print('='*80)
print(f'Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print()

# Step 1: Match using reconciled_receipt_id
print('STEP 1: Using banking_transactions.reconciled_receipt_id')
print('-'*80)

cur.execute('''
    UPDATE receipts r
    SET banking_transaction_id = bt.transaction_id
    FROM banking_transactions bt
    WHERE bt.reconciled_receipt_id = r.receipt_id
    AND r.banking_transaction_id IS NULL
''')

count1 = cur.rowcount
print(f'Matched: {count1:,} receipts')
print()

# Step 2: Match using receipt_id column
print('STEP 2: Using banking_transactions.receipt_id')
print('-'*80)

cur.execute('''
    UPDATE receipts r
    SET banking_transaction_id = bt.transaction_id
    FROM banking_transactions bt
    WHERE bt.receipt_id = r.receipt_id
    AND r.banking_transaction_id IS NULL
''')

count2 = cur.rowcount
print(f'Matched: {count2:,} receipts')
print()

# Step 3: Verify
print('VERIFICATION:')
print('-'*80)

cur.execute('SELECT COUNT(*) FROM receipts WHERE banking_transaction_id IS NOT NULL')
matched = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM receipts')
total = cur.fetchone()[0]

pct = (matched / total * 100) if total > 0 else 0
print(f'Receipts with banking_transaction_id: {matched:,} of {total:,} ({pct:.1f}%)')
print()

# Step 4: Sample matches
print('SAMPLE MATCHES:')
print('-'*80)

cur.execute('''
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.gross_amount,
        bt.transaction_id,
        bt.transaction_date,
        bt.description
    FROM receipts r
    JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
    LIMIT 10
''')

for receipt_id, rec_date, vendor, rec_amount, txn_id, txn_date, txn_desc in cur.fetchall():
    print(f'Receipt {receipt_id}: {vendor[:25]:25} ${float(rec_amount):>10,.2f}')
    print(f'  → Banking Txn {txn_id}: {txn_desc[:50]:50} {txn_date}')
    print()

conn.commit()
print(f'✅ Total updated: {count1 + count2:,} receipts')

cur.close()
conn.close()
