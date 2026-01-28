#!/usr/bin/env python3
"""
Add mapped_bank_account_id to receipts table to identify which bank account
each receipt matched to. Enables color coding by banking account.
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*80)
print('ADDING BANK ACCOUNT MAPPING TO RECEIPTS')
print('='*80)
print(f'Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print()

# Step 1: Check if column exists
cur.execute('''
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'receipts' AND column_name = 'mapped_bank_account_id'
''')

if cur.fetchone():
    print('✅ Column mapped_bank_account_id already exists')
else:
    # Add the column
    cur.execute('ALTER TABLE receipts ADD COLUMN mapped_bank_account_id INTEGER')
    conn.commit()
    print('✅ Added mapped_bank_account_id column')

print()
print('Bank Account Mapping:')
print('  1 = CIBC Checking 0228362')
print('  2 = Scotia Bank 903990106011')
print()

# Step 2: Populate from banking_transactions where linked
print('STEP 1: Mapping from banking_transactions link')
print('-'*80)

cur.execute('''
    UPDATE receipts r
    SET mapped_bank_account_id = CASE 
        WHEN bt.account_number = '0228362' THEN 1
        WHEN bt.account_number = '903990106011' THEN 2
        ELSE NULL
    END
    FROM banking_transactions bt
    WHERE bt.transaction_id = r.banking_transaction_id
    AND r.mapped_bank_account_id IS NULL
''')

linked_count = cur.rowcount
conn.commit()
print(f'Mapped {linked_count:,} receipts from banking_transaction_id link')
print()

# Step 3: Summary by bank account and color
print('='*80)
print('RECEIPTS BY BANK ACCOUNT AND COLOR')
print('='*80)

cur.execute('''
    SELECT 
        CASE mapped_bank_account_id
            WHEN 1 THEN 'CIBC 0228362'
            WHEN 2 THEN 'Scotia 903990106011'
            ELSE 'No bank account'
        END as account,
        display_color,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    GROUP BY mapped_bank_account_id, display_color
    ORDER BY 
        CASE mapped_bank_account_id
            WHEN 1 THEN 1
            WHEN 2 THEN 2
            ELSE 3
        END,
        CASE display_color
            WHEN 'GREEN' THEN 1
            WHEN 'YELLOW' THEN 2
            WHEN 'ORANGE' THEN 3
            WHEN 'BLUE' THEN 4
            WHEN 'RED' THEN 5
            ELSE 6
        END
''')

print(f"{'Bank Account':30} | {'Color':10} | {'Count':>10} | {'Total Amount':>15}")
print('-'*80)

for account, color, count, total in cur.fetchall():
    total_val = float(total) if total else 0.0
    color_str = color if color else 'NULL'
    emoji = {
        'GREEN': '✅',
        'YELLOW': '💰',
        'ORANGE': '👤',
        'BLUE': '📝',
        'RED': '❌'
    }.get(color_str, '❓')
    
    print(f'{account:30} | {emoji} {color_str:8} | {count:>10,} | ${total_val:>14,.2f}')

print()

# Step 4: Get individual account totals
cur.execute('''
    SELECT 
        mapped_bank_account_id,
        CASE mapped_bank_account_id
            WHEN 1 THEN 'CIBC 0228362'
            WHEN 2 THEN 'Scotia 903990106011'
            ELSE 'No bank account'
        END as account,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    GROUP BY mapped_bank_account_id
    ORDER BY mapped_bank_account_id
''')

print('SUMMARY BY BANK ACCOUNT:')
print('-'*80)
for acct_id, account, count, total in cur.fetchall():
    total_val = float(total) if total else 0.0
    print(f'{account:30} | {count:>10,} receipts | ${total_val:>14,.2f}')

print()
print('✅ Bank account mapping complete')

cur.close()
conn.close()
