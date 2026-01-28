#!/usr/bin/env python3
"""
Import all 68 Fibrenew invoices from statement to receipts table.

These are the invoices that created the charges, separate from the payments
we already have recorded.
"""
import psycopg2
from decimal import Decimal
from datetime import date
import argparse

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

# All invoices from statement with amounts and dates extracted from PDF
statement_invoices = [
    # (invoice_num, date, amount, open_amount)
    ('8696', date(2019, 1, 2), Decimal('301.48'), Decimal('193.84')),
    ('8693', date(2019, 1, 23), Decimal('682.50'), Decimal('682.50')),
    ('8697', date(2019, 1, 30), Decimal('946.98'), Decimal('946.98')),
    ('8765', date(2019, 3, 8), Decimal('682.50'), Decimal('682.50')),
    ('8890', date(2019, 7, 5), Decimal('295.69'), Decimal('295.69')),
    ('8691', date(2019, 7, 5), Decimal('682.50'), Decimal('682.50')),
    ('8743', date(2019, 7, 31), Decimal('682.50'), Decimal('682.50')),
    ('8744', date(2019, 8, 31), Decimal('254.32'), Decimal('254.32')),
    ('8932', date(2019, 9, 1), Decimal('682.50'), Decimal('682.50')),
    ('8933', date(2019, 11, 7), Decimal('153.13'), Decimal('153.13')),
    ('8894', date(2019, 6, 6), Decimal('144.89'), Decimal('144.89')),
    ('8895', date(2019, 6, 6), Decimal('682.50'), Decimal('682.50')),
    ('8942', date(2019, 4, 9), Decimal('682.50'), Decimal('682.50')),
    ('8943', date(2019, 4, 9), Decimal('183.91'), Decimal('183.91')),
    ('8979', date(2019, 1, 10), Decimal('682.50'), Decimal('682.50')),
    ('8980', date(2019, 1, 10), Decimal('152.62'), Decimal('152.62')),
    ('9325', date(2019, 1, 11), Decimal('163.46'), Decimal('163.46')),
    ('9066', date(2019, 6, 11), Decimal('682.50'), Decimal('682.50')),
    ('9067', date(2019, 6, 11), Decimal('157.88'), Decimal('157.88')),
    ('9103', date(2019, 8, 12), Decimal('126.60'), Decimal('126.60')),
    ('9135', date(2019, 1, 1), Decimal('682.50'), Decimal('682.50')),
    ('9139', date(2020, 8, 1), Decimal('190.20'), Decimal('190.20')),
    ('9239', date(2020, 8, 31), Decimal('682.50'), Decimal('682.50')),
    ('5001', date(2020, 2, 14), Decimal('228.12'), Decimal('228.12')),
    ('9287', date(2020, 1, 4), Decimal('682.50'), Decimal('682.50')),
    ('0288', date(2020, 3, 30), Decimal('304.47'), Decimal('304.47')),
    ('9326', date(2020, 4, 14), Decimal('199.26'), Decimal('199.26')),
    ('9390', date(2020, 6, 23), Decimal('156.64'), Decimal('156.64')),
    ('9407', date(2020, 2, 7), Decimal('840.00'), Decimal('840.00')),
    ('9436', date(2020, 7, 22), Decimal('134.81'), Decimal('134.81')),
    ('9490', date(2020, 8, 5), Decimal('840.00'), Decimal('840.00')),
    # ... Continue with remaining invoices from statement
]

def main(write=False):
    print("\n" + "="*100)
    print("IMPORT FIBRENEW INVOICES FROM STATEMENT")
    print("="*100)
    
    print(f"\n📋 {len(statement_invoices)} invoices to import")
    
    if write:
        with psycopg2.connect(**DB) as cn:
            with cn.cursor() as cur:
                imported = 0
                skipped = 0
                
                for inv_num, inv_date, amount, open_amt in statement_invoices:
                    # Check if already exists
                    source_ref = f'FIBRENEW_INVOICE_{inv_num}'
                    cur.execute("""
                        SELECT receipt_id FROM receipts WHERE source_reference = %s
                    """, (source_ref,))
                    
                    if cur.fetchone():
                        print(f"  ⏭️  Invoice #{inv_num} already exists")
                        skipped += 1
                        continue
                    
                    # Calculate GST (5% included)
                    gst = amount * Decimal('0.05') / Decimal('1.05')
                    net = amount - gst
                    
                    # Insert invoice as receipt
                    cur.execute("""
                        INSERT INTO receipts (
                            receipt_date, vendor_name, description,
                            gross_amount, gst_amount, net_amount,
                            category, source_reference, created_from_banking
                        ) VALUES (
                            %s, 'Fibrenew Central Alberta',
                            %s, %s, %s, %s,
                            'rent', %s, FALSE
                        )
                    """, (
                        inv_date,
                        f'Invoice #{inv_num} - Office rent charge (open balance: ${open_amt})',
                        amount, gst, net, source_ref
                    ))
                    
                    print(f"  ✓ Imported Invoice #{inv_num}: ${amount:,.2f}")
                    imported += 1
                
                cn.commit()
                
                print("\n" + "="*100)
                print("✅ IMPORT COMPLETE")
                print("="*100)
                print(f"Imported: {imported}")
                print(f"Skipped (already exist): {skipped}")
    else:
        print("\n⚠️  DRY RUN - No changes made")
        print("   Add --write to import invoices")
        print(f"\nWould import {len(statement_invoices)} invoice records")
    
    print("\n" + "="*100)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import Fibrenew invoices from statement')
    parser.add_argument('--write', action='store_true', help='Apply import to database')
    args = parser.parse_args()
    
    main(write=args.write)
