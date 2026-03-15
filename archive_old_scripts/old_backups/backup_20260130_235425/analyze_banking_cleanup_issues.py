#!/usr/bin/env python3
"""
Analyze CIBC banking data cleanup issues:
1. PRE-AUTH DEBIT with vendor info in wrong place
2. Cheque #dd descriptions
3. Heffner/Lexus/Toyota variations
4. X descriptions needing vendor extraction
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*80)
print('ISSUE 1: PRE-AUTH DEBIT entries (vendor info embedded)')
print('='*80)
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND description LIKE '%PRE-AUTH%'
    ORDER BY transaction_date DESC
    LIMIT 10
""")
for tid, date, desc, debit, credit in cur.fetchall():
    debit_str = f'${float(debit):.2f}' if debit else '$0.00'
    credit_str = f'${float(credit):.2f}' if credit else '$0.00'
    print(f'{tid} | {date} | {desc[:60]}')
    print(f'   Debit: {debit_str}, Credit: {credit_str}')
    print()

print('='*80)
print('ISSUE 2: Cheque #dd descriptions (vendor in wrong place)')
print('='*80)
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, vendor_extracted
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND (description LIKE 'Cheque %dd%' OR description LIKE 'Cheque %#dd%')
    ORDER BY transaction_date DESC
    LIMIT 15
""")
for tid, date, desc, debit, vendor in cur.fetchall():
    debit_str = f'${float(debit):.2f}' if debit else '$0.00'
    vendor_str = vendor if vendor else 'NULL'
    print(f'{tid} | {date} | {desc[:60]}')
    print(f'   Amount: {debit_str}, Vendor: {vendor_str}')
    print()

print('='*80)
print('ISSUE 3: Heffner/Lexus/Toyota variations (lease accounts)')
print('='*80)
cur.execute("""
    SELECT DISTINCT description, COUNT(*) as count
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND (description LIKE '%Heffner%' OR description LIKE '%LEXUS%' OR description LIKE '%TOYOTA%')
    GROUP BY description
    ORDER BY count DESC
""")
for desc, count in cur.fetchall():
    print(f'{count:4d} | {desc}')

print()
print('='*80)
print('ISSUE 4: Receiver General variations')
print('='*80)
cur.execute("""
    SELECT DISTINCT description, COUNT(*) as count
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND description LIKE '%Receiver%General%'
    GROUP BY description
    ORDER BY count DESC
""")
for desc, count in cur.fetchall():
    print(f'{count:4d} | {desc}')

print()
print('='*80)
print('ISSUE 5: Centex variations')
print('='*80)
cur.execute("""
    SELECT DISTINCT description, COUNT(*) as count
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND description LIKE '%Centex%'
    GROUP BY description
    ORDER BY count DESC
    LIMIT 20
""")
for desc, count in cur.fetchall():
    print(f'{count:4d} | {desc}')

print()
print('='*80)
print('ISSUE 6: Hertz variations')
print('='*80)
cur.execute("""
    SELECT DISTINCT description, COUNT(*) as count
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND description LIKE '%Hertz%'
    GROUP BY description
    ORDER BY count DESC
""")
for desc, count in cur.fetchall():
    print(f'{count:4d} | {desc}')

cur.close()
conn.close()
