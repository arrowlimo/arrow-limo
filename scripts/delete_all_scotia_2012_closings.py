#!/usr/bin/env python3
"""
Delete all month-end 'X' closing entries from Scotia Bank 2012.
These are reconciliation balance entries, not real transactions.
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*80)
print('DELETING ALL SCOTIA 2012 MONTH-END CLOSING ENTRIES')
print('='*80)
print()

# First, backup by showing what will be deleted
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    AND description = 'X'
    ORDER BY transaction_date DESC
""")

to_delete = cur.fetchall()
print(f'Found {len(to_delete)} month-end entries to delete:')
print()

for tid, date, desc, debit, credit, balance in to_delete:
    debit_str = f'${float(debit):.2f}' if debit else '$0.00'
    credit_str = f'${float(credit):.2f}' if credit else '$0.00'
    balance_str = f'${float(balance):.2f}' if balance else 'NULL'
    print(f'{tid} | {date} | D:{debit_str:>12} C:{credit_str:>12} | Balance: {balance_str}')

print()

# Delete all Scotia 2012 'X' entries
cur.execute("""
    DELETE FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    AND description = 'X'
""")

deleted = cur.rowcount
conn.commit()

print(f'✅ DELETED {deleted} month-end closing entries')
print()

# Verify deletion
cur.execute("""
    SELECT COUNT(*) as remaining
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    AND description = 'X'
""")

remaining = cur.fetchone()[0]
print(f'Remaining "X" entries in Scotia 2012: {remaining}')
print()

# Show final Scotia 2012 transaction count
cur.execute("""
    SELECT 
        COUNT(*) as total_txns,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as total_debits,
        SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as total_credits
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
""")

total, first, last, debits, credits = cur.fetchone()
print(f'Scotia 2012 Final Transaction Count: {total} transactions')
print(f'Date Range: {first} to {last}')
print(f'Total Debits: ${float(debits):,.2f}')
print(f'Total Credits: ${float(credits):,.2f}')
print()

print('✅ Cleanup complete - Scotia 2012 now contains only real transactions')

cur.close()
conn.close()
