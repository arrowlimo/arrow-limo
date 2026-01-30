#!/usr/bin/env python3
"""
Fix remaining Cheque #dd and X artifacts in CIBC banking descriptions.
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*80)
print('FIXING REMAINING CHEQUE #dd AND X ARTIFACTS')
print('='*80)
print()

# Find all remaining patterns
print('Step 1: Check current state')
print('-'*80)

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND (description LIKE 'Cheque %dd%' OR description LIKE 'Cheque %DD%')
""")
dd_count = cur.fetchone()[0]
print(f'Remaining Cheque #dd entries: {dd_count}')

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND description LIKE '% X'
""")
x_count = cur.fetchone()[0]
print(f'Descriptions ending with X: {x_count}')

print()
print('Step 2: Show examples before fix')
print('-'*80)

cur.execute("""
    SELECT transaction_id, description
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND (description LIKE 'Cheque %dd%' OR description LIKE '% X')
    ORDER BY transaction_date DESC
    LIMIT 10
""")

for tid, desc in cur.fetchall():
    print(f'{tid} | {desc}')

print()
print('Step 3: Apply fixes')
print('-'*80)

# Fix 1: Remove " X" suffix from all descriptions
cur.execute("""
    UPDATE banking_transactions
    SET description = TRIM(REGEXP_REPLACE(description, ' X$', '', 'g'))
    WHERE account_number = '0228362'
    AND description LIKE '% X'
""")
x_removed = cur.rowcount
print(f'✅ Removed " X" suffix from {x_removed} descriptions')

# Fix 2: Remove "#dd " from remaining cheque descriptions
cur.execute("""
    UPDATE banking_transactions
    SET description = REGEXP_REPLACE(description, '#dd ', '', 'gi')
    WHERE account_number = '0228362'
    AND (description LIKE '%#dd %' OR description LIKE '%#DD %')
""")
dd_removed = cur.rowcount
print(f'✅ Removed "#dd " from {dd_removed} descriptions')

# Fix 3: Clean up any "Cheque Cheque" duplicates that might have been created
cur.execute("""
    UPDATE banking_transactions
    SET description = REGEXP_REPLACE(description, 'Cheque Cheque', 'Cheque', 'g')
    WHERE account_number = '0228362'
    AND description LIKE '%Cheque Cheque%'
""")
dupe_removed = cur.rowcount
print(f'✅ Fixed {dupe_removed} "Cheque Cheque" duplicates')

print()
print('Step 4: Verify cleanup')
print('-'*80)

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND (description LIKE 'Cheque %dd%' OR description LIKE 'Cheque %DD%')
""")
dd_remaining = cur.fetchone()[0]
print(f'Remaining Cheque #dd entries: {dd_remaining}')

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND description LIKE '% X'
""")
x_remaining = cur.fetchone()[0]
print(f'Remaining " X" suffixes: {x_remaining}')

print()
print('Step 5: Show cleaned examples')
print('-'*80)

cur.execute("""
    SELECT transaction_id, description, vendor_extracted
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND vendor_extracted IN ('Hertz', 'LFG', 'AMEX', 'Staples', 'Husky')
    ORDER BY transaction_date DESC
    LIMIT 10
""")

for tid, desc, vendor in cur.fetchall():
    print(f'{tid} | {desc[:50]} | Vendor: {vendor}')

print()
conn.commit()
print('✅ All fixes committed')

cur.close()
conn.close()
