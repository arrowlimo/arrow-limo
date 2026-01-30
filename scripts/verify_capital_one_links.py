#!/usr/bin/env python3
"""
Verify Capital One receipt-banking links.
Shows the linked payment receipt and summary of all Capital One receipts.
"""

import psycopg2

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()

    print('=' * 80)
    print('CAPITAL ONE PAYMENT RECEIPT → BANKING LINK VERIFICATION')
    print('=' * 80)
    print()

    # Check Capital One payment link
    cur.execute('''
        SELECT 
            r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount, 
            b.transaction_id, b.transaction_date, b.description, b.debit_amount
        FROM receipts r
        JOIN banking_receipt_matching_ledger l ON r.receipt_id = l.receipt_id
        JOIN banking_transactions b ON l.banking_transaction_id = b.transaction_id
        WHERE r.receipt_id = 113027
    ''')
    row = cur.fetchone()

    if row:
        print('[OK] LINK VERIFIED')
        print()
        print('Receipt Side:')
        print(f'  ID: {row[0]}')
        print(f'  Date: {row[1]}')
        print(f'  Vendor: {row[2]}')
        print(f'  Amount: ${row[3]:,.2f}')
        print()
        print('Banking Side:')
        print(f'  ID: {row[4]}')
        print(f'  Date: {row[5]}')
        print(f'  Amount: ${row[7]:,.2f}')
        print(f'  Description: {row[6]}')
        print()
        date_diff = abs((row[1] - row[5]).days)
        print(f'[OK] Date difference: {date_diff} day(s)')
    else:
        print('[FAIL] Link not found for receipt 113027')

    print()
    print('=' * 80)
    print('TOTAL RECEIPT-BANKING LINKS')
    print('=' * 80)
    
    # Check total links
    cur.execute('SELECT COUNT(*) FROM banking_receipt_matching_ledger')
    total = cur.fetchone()[0]
    print(f'Total links in system: {total:,}')

    print()
    print('=' * 80)
    print('CAPITAL ONE RECEIPTS SUMMARY')
    print('=' * 80)
    
    # Check Capital One receipts vs links
    cur.execute('''
        SELECT COUNT(*) 
        FROM receipts 
        WHERE vendor_name LIKE '%Capital One%'
    ''')
    cap_one_receipts = cur.fetchone()[0]

    cur.execute('''
        SELECT COUNT(*) 
        FROM receipts r
        JOIN banking_receipt_matching_ledger l ON r.receipt_id = l.receipt_id
        WHERE r.vendor_name LIKE '%Capital One%'
    ''')
    cap_one_linked = cur.fetchone()[0]

    print(f'Total Capital One receipts: {cap_one_receipts}')
    print(f'Linked to banking: {cap_one_linked}')
    print(f'Unlinked: {cap_one_receipts - cap_one_linked}')
    
    if cap_one_receipts - cap_one_linked > 0:
        print()
        print('Note: Individual CC purchases should NOT be linked to banking.')
        print('      Only payments TO the credit card appear in banking transactions.')
    
    # Show breakdown of Capital One receipts
    print()
    print('Capital One Receipt Breakdown:')
    cur.execute('''
        SELECT 
            CASE 
                WHEN r.vendor_name LIKE '%Payment%' THEN 'Payments'
                WHEN r.vendor_name LIKE '%Interest%' THEN 'Interest Charges'
                WHEN r.vendor_name LIKE '%Fee%' THEN 'Fees'
                ELSE 'Purchases'
            END as type,
            COUNT(*),
            SUM(r.gross_amount)
        FROM receipts r
        WHERE r.vendor_name LIKE '%Capital One%'
        GROUP BY (CASE 
                WHEN r.vendor_name LIKE '%Payment%' THEN 'Payments'
                WHEN r.vendor_name LIKE '%Interest%' THEN 'Interest Charges'
                WHEN r.vendor_name LIKE '%Fee%' THEN 'Fees'
                ELSE 'Purchases'
            END)
        ORDER BY type
    ''')
    
    for row in cur.fetchall():
        print(f'  {row[0]}: {row[1]} receipts, ${row[2]:,.2f}')

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
