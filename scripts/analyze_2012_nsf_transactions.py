#!/usr/bin/env python3
"""Analyze NSF transactions in 2012 to verify they're properly signed and cancel correctly."""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print('='*70)
print('2012 NSF TRANSACTION ANALYSIS')
print('='*70)
print()

# Find all NSF-related transactions in 2012
cur.execute('''
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        description,
        category
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    AND (
        vendor_name ILIKE '%NSF%'
        OR vendor_name ILIKE '%BOUNCE%'
        OR vendor_name ILIKE '%REVERSAL%'
        OR vendor_name ILIKE '%CORRECTION%'
        OR vendor_name ILIKE '%CHARGE BACK%'
        OR description ILIKE '%NSF%'
        OR description ILIKE '%BOUNCE%'
        OR description ILIKE '%REVERSAL%'
    )
    ORDER BY receipt_date, gross_amount
''')

nsf_transactions = cur.fetchall()

print(f'Found {len(nsf_transactions)} NSF-related transactions in 2012')
print()

if nsf_transactions:
    print('NSF Transaction Details:')
    print('-'*70)
    total_positive = 0
    total_negative = 0
    
    for rec in nsf_transactions:
        rec_id, date, vendor, amount, desc, category = rec
        sign = '+' if amount > 0 else '-'
        if amount > 0:
            total_positive += amount
        else:
            total_negative += amount
        
        print(f'{sign} {date} | ${amount:>10,.2f} | {vendor[:40]}')
    
    print('-'*70)
    print(f'Total Positive (charges): ${total_positive:,.2f}')
    print(f'Total Negative (reversals): ${total_negative:,.2f}')
    print(f'Net Impact: ${total_positive + total_negative:,.2f}')
    print()
    
    if abs(total_positive + total_negative) < 0.01:
        print('✅ NSF transactions cancel out perfectly!')
    elif abs(total_positive + total_negative) < 50:
        print('✅ Small net impact (likely acceptable)')
    else:
        print('⚠️  WARNING: Significant net impact from NSF transactions')
else:
    print('No NSF transactions found in 2012 receipts')

cur.close()
conn.close()
