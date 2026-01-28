"""Analyze unmatched debit transactions to see which should have receipts."""

import psycopg2

conn = psycopg2.connect(
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***',
    host='localhost'
)
cur = conn.cursor()

print('='*80)
print('UNMATCHED DEBIT (EXPENSE) ANALYSIS')
print('='*80)
print()

# Get all unmatched debits by account
cur.execute('''
    SELECT 
        bt.account_number,
        COUNT(*) as count,
        SUM(bt.debit_amount) as total_amount,
        MIN(bt.transaction_date) as first_date,
        MAX(bt.transaction_date) as last_date
    FROM banking_transactions bt
    WHERE bt.debit_amount > 0
    AND NOT EXISTS (
        SELECT 1 FROM banking_receipt_matching_ledger bm
        WHERE bm.banking_transaction_id = bt.transaction_id
    )
    GROUP BY bt.account_number
    ORDER BY count DESC
''')

print('Unmatched Debits by Account:')
print('-'*80)
total_unmatched_debits = 0
total_unmatched_amount = 0
for row in cur.fetchall():
    acc, count, amount, first, last = row
    total_unmatched_debits += count
    total_unmatched_amount += amount or 0
    print(f'{acc:15s}: {count:6,} debits | ${amount:>12,.2f} | {first} to {last}')
print(f'{"TOTAL":15s}: {total_unmatched_debits:6,} debits | ${total_unmatched_amount:>12,.2f}')
print()

# Analyze by vendor/description pattern for CIBC
print('CIBC (0228362) Unmatched Debits by Vendor:')
print('-'*80)
cur.execute('''
    SELECT 
        COALESCE(vendor_extracted, LEFT(description, 30)) as vendor,
        COUNT(*) as count,
        SUM(debit_amount) as total_amount
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND debit_amount > 0
    AND NOT EXISTS (
        SELECT 1 FROM banking_receipt_matching_ledger bm
        WHERE bm.banking_transaction_id = transaction_id
    )
    GROUP BY COALESCE(vendor_extracted, LEFT(description, 30))
    ORDER BY count DESC
    LIMIT 20
''')
print(f'{"Vendor/Description":<40s} {"Count":>6s} {"Amount":>15s}')
print('-'*80)
for row in cur.fetchall():
    vendor, count, amount = row
    print(f'{vendor[:40]:<40s} {count:>6,} ${amount:>14,.2f}')
print()

# Analyze by vendor/description for Scotia
print('Scotia (903990106011) Unmatched Debits by Vendor:')
print('-'*80)
cur.execute('''
    SELECT 
        COALESCE(vendor_extracted, LEFT(description, 30)) as vendor,
        COUNT(*) as count,
        SUM(debit_amount) as total_amount
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND debit_amount > 0
    AND NOT EXISTS (
        SELECT 1 FROM banking_receipt_matching_ledger bm
        WHERE bm.banking_transaction_id = transaction_id
    )
    GROUP BY COALESCE(vendor_extracted, LEFT(description, 30))
    ORDER BY count DESC
    LIMIT 20
''')
print(f'{"Vendor/Description":<40s} {"Count":>6s} {"Amount":>15s}')
print('-'*80)
for row in cur.fetchall():
    vendor, count, amount = row
    print(f'{vendor[:40]:<40s} {count:>6,} ${amount:>14,.2f}')
print()

# Check if receipts exist for these transactions (matching on date/amount)
print('Checking if receipts exist that could match unmatched debits...')
print('-'*80)
cur.execute('''
    SELECT 
        COUNT(DISTINCT bt.transaction_id) as unmatched_with_potential_receipt
    FROM banking_transactions bt
    WHERE bt.debit_amount > 0
    AND NOT EXISTS (
        SELECT 1 FROM banking_receipt_matching_ledger bm
        WHERE bm.banking_transaction_id = bt.transaction_id
    )
    AND EXISTS (
        SELECT 1 FROM receipts r
        WHERE r.receipt_date = bt.transaction_date
        AND ABS(r.gross_amount - bt.debit_amount) < 0.01
    )
''')
potential_matches = cur.fetchone()[0]
print(f'Unmatched debits with potential receipt match: {potential_matches:,}')
print()

# Sample these potential matches
if potential_matches > 0:
    print('Sample Potential Matches (unmatched banking debits with matching receipts):')
    print('-'*80)
    cur.execute('''
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.account_number,
            bt.debit_amount,
            COALESCE(bt.vendor_extracted, LEFT(bt.description, 40)) as bank_vendor,
            r.vendor_name as receipt_vendor,
            r.receipt_id
        FROM banking_transactions bt
        JOIN receipts r ON r.receipt_date = bt.transaction_date 
            AND ABS(r.gross_amount - bt.debit_amount) < 0.01
        WHERE bt.debit_amount > 0
        AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger bm
            WHERE bm.banking_transaction_id = bt.transaction_id
        )
        ORDER BY bt.debit_amount DESC
        LIMIT 20
    ''')
    print(f'{"Date":<12s} {"Account":<15s} {"Amount":>10s} {"Bank Vendor":<30s} {"Receipt Vendor":<30s}')
    print('-'*80)
    for row in cur.fetchall():
        txn_id, date, acc, amount, bank_v, receipt_v, rid = row
        print(f'{str(date):<12s} {acc:<15s} ${amount:>9,.2f} {(bank_v or "")[:30]:<30s} {(receipt_v or "")[:30]:<30s}')
    print()
    print(f'✓ Found {potential_matches:,} unmatched banking debits that have matching receipts!')
    print('  These can be linked using the match_all_receipts_to_banking.py script.')

cur.close()
conn.close()
