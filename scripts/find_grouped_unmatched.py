#!/usr/bin/env python3
"""
Find groups of unmatched banking transactions by amount and vendor pattern.
Identifies recurring transactions that could be documented together.
"""

import psycopg2
from collections import defaultdict

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Find unmatched 2012 Scotia debits grouped by amount and vendor pattern
cur.execute('''
    SELECT 
        debit_amount,
        description,
        COUNT(*) as occurrence_count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        SUM(debit_amount) as total_amount,
        ARRAY_AGG(transaction_id ORDER BY transaction_date) as trans_ids
    FROM banking_transactions
    WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        AND debit_amount > 0
        AND transaction_id NOT IN (
            SELECT mapped_bank_account_id 
            FROM receipts 
            WHERE mapped_bank_account_id IS NOT NULL
        )
    GROUP BY debit_amount, description
    HAVING COUNT(*) >= 2
    ORDER BY COUNT(*) DESC, debit_amount DESC
    LIMIT 30
''')

groups = cur.fetchall()

print('=' * 120)
print('GROUPED UNMATCHED TRANSACTIONS (2+ occurrences)')
print('=' * 120)
print(f"{'Amount':<12} {'Count':<6} {'Total':<12} {'First Date':<12} {'Last Date':<12} {'Description':<50}")
print('-' * 120)

for amount, desc, count, first_date, last_date, total, trans_ids in groups:
    print(f"${amount:>10.2f} {count:>5}x ${total:>10.2f} {str(first_date):<12} {str(last_date):<12} {desc[:50]}")

print()
print('=' * 120)
print('VENDOR PATTERN ANALYSIS')
print('=' * 120)

# Extract vendor patterns
cur.execute('''
    SELECT 
        CASE 
            WHEN description ILIKE '%CHQ%' THEN 'CHEQUE'
            WHEN description ILIKE '%RENT%LEASE%' OR description ILIKE '%LEASE%' THEN 'LEASE/RENT'
            WHEN description ILIKE '%SGI%' THEN 'SGI'
            WHEN description ILIKE '%HEFFNER%' THEN 'HEFFNER'
            WHEN description ILIKE '%INSURANCE%' THEN 'INSURANCE'
            WHEN description ILIKE '%LOAN%' THEN 'LOAN'
            WHEN description ILIKE '%TRANSFER%' THEN 'TRANSFER'
            WHEN description ILIKE '%POS%' THEN 'POS'
            WHEN description ILIKE '%PAD%' THEN 'PRE-AUTH DEBIT'
            ELSE 'OTHER'
        END as vendor_type,
        COUNT(*) as count,
        SUM(debit_amount) as total_amount
    FROM banking_transactions
    WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        AND debit_amount > 0
        AND transaction_id NOT IN (
            SELECT mapped_bank_account_id 
            FROM receipts 
            WHERE mapped_bank_account_id IS NOT NULL
        )
    GROUP BY vendor_type
    ORDER BY count DESC
''')

patterns = cur.fetchall()
for vendor_type, count, total in patterns:
    print(f"{vendor_type:<20} {count:>4} transactions ${total:>12,.2f}")

print()
print('=' * 120)
print('TOP RECURRING VENDORS (3+ occurrences)')
print('=' * 120)

# Find specific recurring vendors
cur.execute('''
    WITH vendor_extract AS (
        SELECT 
            transaction_id,
            debit_amount,
            transaction_date,
            description,
            CASE 
                WHEN description ILIKE '%HEFFNER%' THEN 'Heffner Auto Finance'
                WHEN description ILIKE '%SGI%' THEN 'SGI (Insurance/Registration)'
                WHEN description ILIKE '%OFFICE RENT%' OR description ILIKE '%RENT/LEASES%2695%' THEN 'Office/Equipment Rent'
                WHEN description ILIKE '%SASKTEL%' THEN 'SaskTel'
                WHEN description ILIKE '%CIBC%' THEN 'CIBC (fees/services)'
                WHEN description ILIKE '%PAYROLL%' THEN 'Payroll'
                ELSE 'Other'
            END as vendor_name
        FROM banking_transactions
        WHERE account_number = '903990106011'
            AND EXTRACT(YEAR FROM transaction_date) = 2012
            AND debit_amount > 0
            AND transaction_id NOT IN (
                SELECT mapped_bank_account_id 
                FROM receipts 
                WHERE mapped_bank_account_id IS NOT NULL
            )
    )
    SELECT 
        vendor_name,
        COUNT(*) as count,
        SUM(debit_amount) as total,
        MIN(debit_amount) as min_amt,
        MAX(debit_amount) as max_amt,
        ROUND(AVG(debit_amount)::numeric, 2) as avg_amt
    FROM vendor_extract
    WHERE vendor_name != 'Other'
    GROUP BY vendor_name
    HAVING COUNT(*) >= 3
    ORDER BY COUNT(*) DESC
''')

vendors = cur.fetchall()
for vendor, count, total, min_amt, max_amt, avg_amt in vendors:
    print(f"{vendor:<30} {count:>3}x  Total: ${total:>10,.2f}  Avg: ${avg_amt:>8.2f}  Range: ${min_amt:.2f}-${max_amt:.2f}")

cur.close()
conn.close()
