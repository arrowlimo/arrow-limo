#!/usr/bin/env python3
"""
Generate color-coded receipt report for easy visual review.
Exports to CSV with color coding and reconciliation status.
"""

import psycopg2
import csv
from datetime import datetime

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_file = f'l:/limo/reports/receipts_color_coded_{timestamp}.csv'

print('='*80)
print('GENERATING COLOR-CODED RECEIPT REPORT')
print('='*80)
print(f'Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print()

# Fetch all receipts with banking details
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.gross_amount,
        r.category,
        r.receipt_source,
        r.display_color,
        r.banking_transaction_id,
        bt.transaction_date as bank_date,
        bt.description as bank_description,
        bt.debit_amount as bank_amount,
        CASE 
            WHEN r.banking_transaction_id IS NOT NULL THEN '✅ MATCHED'
            WHEN r.receipt_source = 'CASH' THEN '💰 CASH BOX'
            WHEN r.receipt_source = 'REIMBURSEMENT' THEN '👤 EMPLOYEE'
            WHEN r.receipt_source = 'MANUAL' THEN '📝 MANUAL'
            WHEN r.receipt_source = 'UNMATCHED' THEN '❌ NEEDS REVIEW'
            ELSE '❓ UNKNOWN'
        END as status
    FROM receipts r
    LEFT JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
    ORDER BY r.receipt_date DESC, r.receipt_id DESC
""")

receipts = cur.fetchall()

print(f'Fetched: {len(receipts):,} receipts')
print(f'Writing to: {output_file}')
print()

# Write CSV with color coding
with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    
    # Header
    writer.writerow([
        'Receipt ID', 'Receipt Date', 'Vendor', 'Amount', 'Category',
        'Source', 'Color', 'Status', 'Banking Txn ID', 'Bank Date', 
        'Bank Description', 'Bank Amount', 'Date Diff', 'Amount Diff'
    ])
    
    # Data rows
    for row in receipts:
        receipt_id, receipt_date, vendor, amount, category, source, color, \
            bank_txn_id, bank_date, bank_desc, bank_amount, status = row
        
        # Calculate differences
        date_diff = ''
        amount_diff = ''
        if bank_date and receipt_date:
            date_diff = (bank_date - receipt_date).days
        if bank_amount and amount:
            amount_diff = f'{float(bank_amount) - float(amount):.2f}'
        
        writer.writerow([
            receipt_id,
            receipt_date,
            vendor or '',
            f'{float(amount):.2f}' if amount else '0.00',
            category or '',
            source or '',
            color or '',
            status,
            bank_txn_id or '',
            bank_date or '',
            bank_desc or '',
            f'{float(bank_amount):.2f}' if bank_amount else '',
            date_diff,
            amount_diff
        ])

print(f'✅ Report saved: {output_file}')
print()

# Summary by color
print('SUMMARY BY COLOR:')
print('-'*80)

cur.execute("""
    SELECT 
        display_color,
        receipt_source,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    GROUP BY display_color, receipt_source
    ORDER BY 
        CASE display_color
            WHEN 'GREEN' THEN 1
            WHEN 'YELLOW' THEN 2
            WHEN 'ORANGE' THEN 3
            WHEN 'BLUE' THEN 4
            WHEN 'RED' THEN 5
            ELSE 6
        END
""")

for color, source, count, total in cur.fetchall():
    emoji = {
        'GREEN': '✅',
        'YELLOW': '💰',
        'ORANGE': '👤',
        'BLUE': '📝',
        'RED': '❌'
    }.get(color or '', '❓')
    
    total_val = float(total) if total else 0.0
    print(f'{emoji} {color or "NULL":10} | {source or "NULL":20} | {count:>8,} receipts | ${total_val:>15,.2f}')

print()
print('COLOR LEGEND:')
print('  ✅ GREEN  = Matched to banking transaction')
print('  💰 YELLOW = Cash payment (no banking expected)')
print('  👤 ORANGE = Employee reimbursement')
print('  📝 BLUE   = Manually entered (may need matching)')
print('  ❌ RED    = Unmatched (needs review)')
print()

cur.close()
conn.close()
