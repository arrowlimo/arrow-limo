#!/usr/bin/env python3
"""
Fix blank descriptions by using vendor_extracted data.
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*80)
print('FIXING BLANK DESCRIPTIONS')
print('='*80)
print()

print('Step 1: Show blank entries before fix')
print('-'*80)

cur.execute("""
    SELECT 
        transaction_id,
        account_number,
        transaction_date,
        description,
        vendor_extracted,
        debit_amount,
        credit_amount
    FROM banking_transactions
    WHERE description IS NULL OR TRIM(description) = ''
    ORDER BY transaction_date
""")

blank_entries = cur.fetchall()
print(f'Found {len(blank_entries)} blank descriptions:')
for tid, acc, date, desc, vendor, debit, credit in blank_entries:
    print(f'{tid} | {date} | Vendor: {vendor or "NONE"} | ${debit or 0:.2f}/${credit or 0:.2f}')

print()
print('Step 2: Update descriptions from vendor_extracted')
print('-'*80)

cur.execute("""
    UPDATE banking_transactions
    SET description = vendor_extracted
    WHERE (description IS NULL OR TRIM(description) = '')
    AND vendor_extracted IS NOT NULL
    AND TRIM(vendor_extracted) != ''
""")

updated_count = cur.rowcount
print(f'✅ Updated {updated_count} descriptions from vendor_extracted')

print()
print('Step 3: Check remaining blanks')
print('-'*80)

cur.execute("""
    SELECT 
        transaction_id,
        account_number,
        transaction_date,
        description,
        vendor_extracted,
        debit_amount,
        credit_amount
    FROM banking_transactions
    WHERE description IS NULL OR TRIM(description) = ''
    ORDER BY transaction_date
""")

remaining = cur.fetchall()
if remaining:
    print(f'⚠️  Still {len(remaining)} blank descriptions (no vendor data):')
    for tid, acc, date, desc, vendor, debit, credit in remaining:
        print(f'{tid} | {acc} | {date} | ${debit or 0:.2f}/${credit or 0:.2f}')
else:
    print('✅ No remaining blank descriptions')

print()
print('Step 4: Verify fixed entries')
print('-'*80)

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount
    FROM banking_transactions
    WHERE transaction_id IN (
        SELECT transaction_id FROM (VALUES 
            (62890), (62775), (62623), (48884), (48864), 
            (48863), (48834), (48819), (48810), (48808),
            (48737), (48736)
        ) AS t(transaction_id)
    )
    ORDER BY transaction_date
""")

print('Fixed entries now show:')
for tid, date, desc, debit, credit in cur.fetchall():
    print(f'{tid} | {date} | {desc} | ${debit or 0:.2f}/${credit or 0:.2f}')

print()
conn.commit()
print('✅ All changes committed')

cur.close()
conn.close()
