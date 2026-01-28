#!/usr/bin/env python3
"""
Find and analyze blank descriptions in banking_transactions.
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*80)
print('ANALYZING BLANK DESCRIPTIONS IN BANKING_TRANSACTIONS')
print('='*80)
print()

print('Step 1: Count blank descriptions')
print('-'*80)

# Check various types of "blank"
cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE description IS NULL) as null_count,
        COUNT(*) FILTER (WHERE description = '') as empty_string_count,
        COUNT(*) FILTER (WHERE TRIM(description) = '') as whitespace_only_count,
        COUNT(*) FILTER (WHERE description IS NULL OR TRIM(description) = '') as total_blank
    FROM banking_transactions
""")

null_cnt, empty_cnt, ws_cnt, total_blank = cur.fetchone()
print(f'NULL descriptions: {null_cnt}')
print(f'Empty string descriptions: {empty_cnt}')
print(f'Whitespace-only descriptions: {ws_cnt}')
print(f'TOTAL BLANK: {total_blank}')

print()
print('Step 2: Blank descriptions by account')
print('-'*80)

cur.execute("""
    SELECT 
        account_number,
        COUNT(*) as blank_count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE description IS NULL OR TRIM(description) = ''
    GROUP BY account_number
    ORDER BY blank_count DESC
""")

print('Account | Blank Count | Date Range')
for acc, cnt, first, last in cur.fetchall():
    print(f'{acc} | {cnt} | {first} to {last}')

print()
print('Step 3: Sample blank entries with other data')
print('-'*80)

cur.execute("""
    SELECT 
        transaction_id,
        account_number,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance,
        vendor_extracted
    FROM banking_transactions
    WHERE description IS NULL OR TRIM(description) = ''
    ORDER BY transaction_date DESC
    LIMIT 30
""")

print('TID | Account | Date | Description | Debit | Credit | Balance | Vendor')
print('-'*100)
for tid, acc, date, desc, debit, credit, bal, vendor in cur.fetchall():
    desc_display = 'NULL' if desc is None else f"'{desc}'"
    print(f'{tid} | {acc} | {date} | {desc_display} | ${debit or 0:.2f} | ${credit or 0:.2f} | ${bal or 0:.2f} | {vendor or ""}')

print()
print('Step 4: Check if these have amounts but no description')
print('-'*80)

cur.execute("""
    SELECT 
        COUNT(*) as count,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits
    FROM banking_transactions
    WHERE (description IS NULL OR TRIM(description) = '')
    AND (debit_amount > 0 OR credit_amount > 0)
""")

cnt, debits, credits = cur.fetchone()
print(f'Blank descriptions with amounts: {cnt}')
print(f'Total debits: ${debits or 0:,.2f}')
print(f'Total credits: ${credits or 0:,.2f}')

cur.close()
conn.close()
