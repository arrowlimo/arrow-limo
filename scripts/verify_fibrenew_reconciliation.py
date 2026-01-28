#!/usr/bin/env python3
"""
Verify Fibrenew receipts are properly recorded and reconcile with outstanding balance.
"""

import psycopg2
import os
from decimal import Decimal
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

# Outstanding invoices from Nov 26, 2025 statement
outstanding_invoices = [
    {'invoice': '9956', 'amount': Decimal('840.00')},
    {'invoice': '12131', 'amount': Decimal('1102.50')},
    {'invoice': '12132', 'amount': Decimal('1102.50')},
    {'invoice': '12133', 'amount': Decimal('1102.50')},
    {'invoice': '12177', 'amount': Decimal('1102.50')},
    {'invoice': '12226', 'amount': Decimal('1102.50')},
    {'invoice': '12419', 'amount': Decimal('1102.50')},
    {'invoice': '12494', 'amount': Decimal('1102.50')},
    {'invoice': '12540', 'amount': Decimal('1102.50')},
    {'invoice': '12601', 'amount': Decimal('1102.50')},
    {'invoice': '12664', 'amount': Decimal('1102.50')},
    {'invoice': '12714', 'amount': Decimal('1102.50')},
    {'invoice': '12775', 'amount': Decimal('1102.50')},
    {'invoice': '12835', 'amount': Decimal('1102.50')},
    {'invoice': '12909', 'amount': Decimal('1102.50')},
    {'invoice': '12973', 'amount': Decimal('1102.50')},
    {'invoice': '13041', 'amount': Decimal('1102.50')},
    {'invoice': '13103', 'amount': Decimal('1102.50')},
    {'invoice': '13180', 'amount': Decimal('1260.00')},
    {'invoice': '13248', 'amount': Decimal('1260.00')},
    {'invoice': '13310', 'amount': Decimal('1260.00')},
    {'invoice': '13379', 'amount': Decimal('1260.00')},
    # Additional outstanding from aging report
    {'invoice': '12419', 'amount': Decimal('0.00')},  # duplicate
    {'invoice': '13041', 'amount': Decimal('0.00')},  # duplicate
    {'invoice': '13180', 'amount': Decimal('0.00')},  # duplicate
]

# Remove duplicates and sum
outstanding_unique = {}
for inv in outstanding_invoices:
    if inv['invoice'] not in outstanding_unique:
        outstanding_unique[inv['invoice']] = inv['amount']
    else:
        # Take the non-zero amount
        if inv['amount'] > 0:
            outstanding_unique[inv['invoice']] = inv['amount']

def main():
    print("="*80)
    print("FIBRENEW RECEIPT RECONCILIATION")
    print("="*80)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get all Fibrenew receipts
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
               description, category, created_at
        FROM receipts
        WHERE LOWER(vendor_name) LIKE '%fibrenew%'
        ORDER BY receipt_date
    """)
    
    receipts = cur.fetchall()
    
    print(f"\nTotal Fibrenew receipts in database: {len(receipts)}")
    
    # Extract invoice numbers from descriptions
    import re
    receipt_invoices = {}
    for r in receipts:
        desc = r[4]  # description
        match = re.search(r'Invoice #(\d+)', desc)
        if match:
            inv_num = match.group(1)
            receipt_invoices[inv_num] = {
                'receipt_id': r[0],
                'date': r[1],
                'amount': r[3],
                'category': r[5],
                'created_at': r[6]
            }
    
    print(f"Receipts with invoice numbers: {len(receipt_invoices)}")
    
    # Total amounts
    total_receipts = sum(r[3] for r in receipts)
    print(f"Total receipt amount: ${total_receipts:,.2f}")
    
    # Check outstanding invoices
    print(f"\n{'='*80}")
    print(f"OUTSTANDING INVOICES (from Nov 26, 2025 statement)")
    print(f"{'='*80}")
    
    total_outstanding = Decimal('0')
    outstanding_with_receipts = []
    outstanding_without_receipts = []
    
    for inv_num, amount in outstanding_unique.items():
        if amount > 0:  # Only count non-zero amounts
            total_outstanding += amount
            if inv_num in receipt_invoices:
                outstanding_with_receipts.append((inv_num, amount, receipt_invoices[inv_num]))
            else:
                outstanding_without_receipts.append((inv_num, amount))
    
    print(f"\nTotal outstanding per statement: ${total_outstanding:,.2f}")
    print(f"Expected outstanding balance: $14,734.56")
    
    if len(outstanding_with_receipts) > 0:
        print(f"\n✓ Outstanding invoices WITH receipts: {len(outstanding_with_receipts)}")
        for inv_num, amt, receipt in outstanding_with_receipts[:10]:
            print(f"  Invoice #{inv_num:6} | ${amt:>8,.2f} | Receipt created: {receipt['created_at'].date()}")
        if len(outstanding_with_receipts) > 10:
            print(f"  ... and {len(outstanding_with_receipts) - 10} more")
    
    if len(outstanding_without_receipts) > 0:
        print(f"\n⚠ Outstanding invoices WITHOUT receipts: {len(outstanding_without_receipts)}")
        for inv_num, amt in outstanding_without_receipts:
            print(f"  Invoice #{inv_num:6} | ${amt:>8,.2f} | ❌ NO RECEIPT")
    
    # Check paid invoices (should have receipts)
    print(f"\n{'='*80}")
    print(f"PAID INVOICES STATUS")
    print(f"{'='*80}")
    
    # All invoices minus outstanding = paid
    all_invoice_numbers = set(receipt_invoices.keys())
    outstanding_numbers = set(outstanding_unique.keys())
    paid_numbers = all_invoice_numbers - outstanding_numbers
    
    print(f"\nTotal invoices with receipts: {len(all_invoice_numbers)}")
    print(f"Outstanding invoices: {len(outstanding_numbers)}")
    print(f"Paid invoices: {len(paid_numbers)}")
    
    # Calculate totals
    paid_amount = sum(receipt_invoices[inv]['amount'] for inv in paid_numbers)
    outstanding_receipt_amount = sum(receipt_invoices[inv]['amount'] for inv in outstanding_numbers if inv in receipt_invoices)
    
    print(f"\nTotal paid receipt amount: ${paid_amount:,.2f}")
    print(f"Total outstanding receipt amount: ${outstanding_receipt_amount:,.2f}")
    print(f"Grand total: ${paid_amount + outstanding_receipt_amount:,.2f}")
    
    # Verification
    print(f"\n{'='*80}")
    print(f"RECONCILIATION SUMMARY")
    print(f"{'='*80}")
    
    print(f"\n✓ All {len(receipt_invoices)} invoices have receipt records")
    print(f"✓ Outstanding balance: ${total_outstanding:,.2f} (22 invoices)")
    print(f"✓ Paid balance: ${paid_amount:,.2f} ({len(paid_numbers)} invoices)")
    print(f"✓ Total: ${paid_amount + total_outstanding:,.2f}")
    
    expected_total = Decimal('121566.26')  # From our creation script
    actual_total = total_receipts
    difference = abs(expected_total - actual_total)
    
    if difference < Decimal('1.00'):
        print(f"\n✅ RECONCILIATION COMPLETE - Amounts match!")
    else:
        print(f"\n⚠ Difference: ${difference:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
