#!/usr/bin/env python3
"""
Intelligent receipt-to-banking matching for unmatched receipts.
Uses multiple strategies: exact match, fuzzy date/amount, vendor patterns.
"""

import psycopg2
from datetime import datetime, timedelta
import re

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*80)
print('INTELLIGENT RECEIPT-TO-BANKING MATCHING')
print('='*80)
print(f'Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print()

def normalize_vendor(vendor):
    """Normalize vendor name for matching."""
    if not vendor:
        return ""
    vendor = vendor.upper().strip()
    # Remove common prefixes
    vendor = re.sub(r'^(PURCHASE|DEBIT|PRE-AUTH|CHEQUE|CHQ|WITHDRAWAL)\s+', '', vendor)
    # Remove location codes
    vendor = re.sub(r'\b(RED DEER|LETHBRIDGE|CALGARY|EDMONTON)\s+AB\b', '', vendor)
    # Remove card numbers
    vendor = re.sub(r'\d{4}\*+\d{3,4}', '', vendor)
    # Collapse whitespace
    vendor = re.sub(r'\s+', ' ', vendor).strip()
    return vendor

# Strategy 1: Exact match (date, amount, vendor)
print('STRATEGY 1: Exact Date + Amount + Vendor Match')
print('-'*80)

cur.execute("""
    WITH matched AS (
        SELECT DISTINCT ON (r.receipt_id)
            r.receipt_id,
            bt.transaction_id
        FROM receipts r
        JOIN banking_transactions bt ON 
            bt.transaction_date = r.receipt_date
            AND bt.debit_amount = r.gross_amount
            AND UPPER(bt.description) LIKE '%' || UPPER(r.vendor_name) || '%'
        WHERE r.banking_transaction_id IS NULL
        AND r.receipt_source IN ('UNMATCHED', 'NULL')
        AND bt.debit_amount > 0
        ORDER BY r.receipt_id, bt.transaction_id
    )
    UPDATE receipts r
    SET banking_transaction_id = m.transaction_id,
        receipt_source = 'BANKING',
        display_color = 'GREEN'
    FROM matched m
    WHERE r.receipt_id = m.receipt_id
""")

exact_count = cur.rowcount
print(f'Matched: {exact_count:,} receipts')
conn.commit()
print()

# Strategy 2: Near date (±3 days) + exact amount
print('STRATEGY 2: Near Date (±3 days) + Exact Amount')
print('-'*80)

cur.execute("""
    WITH matched AS (
        SELECT DISTINCT ON (r.receipt_id)
            r.receipt_id,
            bt.transaction_id
        FROM receipts r
        JOIN banking_transactions bt ON 
            bt.transaction_date BETWEEN r.receipt_date - INTERVAL '3 days' 
                                    AND r.receipt_date + INTERVAL '3 days'
            AND bt.debit_amount = r.gross_amount
        WHERE r.banking_transaction_id IS NULL
        AND r.receipt_source IN ('UNMATCHED', 'NULL')
        AND bt.debit_amount > 0
        ORDER BY r.receipt_id, ABS(bt.transaction_date - r.receipt_date)
    )
    UPDATE receipts r
    SET banking_transaction_id = m.transaction_id,
        receipt_source = 'BANKING',
        display_color = 'GREEN'
    FROM matched m
    WHERE r.receipt_id = m.receipt_id
""")

near_count = cur.rowcount
print(f'Matched: {near_count:,} receipts')
conn.commit()
print()

# Strategy 3: Exact date + amount within 5%
print('STRATEGY 3: Exact Date + Amount Within 5%')
print('-'*80)

cur.execute("""
    WITH matched AS (
        SELECT DISTINCT ON (r.receipt_id)
            r.receipt_id,
            bt.transaction_id
        FROM receipts r
        JOIN banking_transactions bt ON 
            bt.transaction_date = r.receipt_date
            AND bt.debit_amount BETWEEN r.gross_amount * 0.95 AND r.gross_amount * 1.05
        WHERE r.banking_transaction_id IS NULL
        AND r.receipt_source IN ('UNMATCHED', 'NULL')
        AND bt.debit_amount > 0
        ORDER BY r.receipt_id, ABS(bt.debit_amount - r.gross_amount)
    )
    UPDATE receipts r
    SET banking_transaction_id = m.transaction_id,
        receipt_source = 'BANKING',
        display_color = 'GREEN'
    FROM matched m
    WHERE r.receipt_id = m.receipt_id
""")

fuzzy_count = cur.rowcount
print(f'Matched: {fuzzy_count:,} receipts')
conn.commit()
print()

# Strategy 4: Handle NULL category (check if should be CASH or MANUAL)
print('STRATEGY 4: Categorizing NULL receipts')
print('-'*80)

cur.execute("""
    UPDATE receipts
    SET receipt_source = 'MANUAL',
        display_color = 'BLUE'
    WHERE receipt_source IS NULL
    AND banking_transaction_id IS NULL
""")

manual_count = cur.rowcount
print(f'Categorized: {manual_count:,} as MANUAL (BLUE)')
conn.commit()
print()

# Summary
print('='*80)
print('MATCHING SUMMARY')
print('='*80)

cur.execute("""
    SELECT 
        receipt_source,
        display_color,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    GROUP BY receipt_source, display_color
    ORDER BY 
        CASE receipt_source
            WHEN 'BANKING' THEN 1
            WHEN 'CASH' THEN 2
            WHEN 'REIMBURSEMENT' THEN 3
            WHEN 'MANUAL' THEN 4
            WHEN 'UNMATCHED' THEN 5
            ELSE 6
        END
""")

print(f"{'Source':20} | {'Color':10} | {'Count':>10} | {'Total Amount':>15}")
print('-'*70)
total_receipts = 0
total_amount = 0
for source, color, count, amount in cur.fetchall():
    amount_val = float(amount) if amount else 0.0
    total_receipts += count
    total_amount += amount_val
    print(f'{source:20} | {color:10} | {count:>10,} | ${amount_val:>14,.2f}')

print('-'*70)
print(f'{"TOTAL":20} | {"":10} | {total_receipts:>10,} | ${total_amount:>14,.2f}')
print()

print(f'✅ Newly matched: {exact_count + near_count + fuzzy_count:,} receipts')
print()

cur.close()
conn.close()
