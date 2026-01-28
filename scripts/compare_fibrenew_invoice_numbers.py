#!/usr/bin/env python3
"""
Compare invoice numbers from Fibrenew statement against database receipts table.
"""
import psycopg2
from decimal import Decimal

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

# All invoice numbers from statement
statement_invoices = {
    '8690', '8691', '8693', '8695', '8696', '8697', '8743', '8744', '8832', '8833',
    '8894', '8895', '8942', '8943', '8979', '8980', '9025', '9066', '9067', '9103',
    '9135', '9139', '9172', '9201', '9239', '9287', '9288', '9325', '9392', '9407',
    '9436', '9490', '9542', '9561', '9609', '9623', '9670', '9694', '9727', '9742',
    '9767', '9772', '9800', '9815', '9866', '9885', '9956', '12131', '12132', '12133',
    '12177', '12226', '12419', '12494', '12540', '12601', '12664', '12714', '12775',
    '12835', '12909', '12973', '13041', '13103', '13180', '13248', '13310', '13379'
}

print("\n" + "="*100)
print("FIBRENEW INVOICE COMPARISON")
print("="*100)

with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        # Check receipts table for Fibrenew invoices
        cur.execute("""
            SELECT receipt_id, receipt_date, vendor_name, description, 
                   gross_amount, source_reference
            FROM receipts
            WHERE vendor_name ILIKE '%fibrenew%'
            OR description ILIKE '%fibrenew%'
            ORDER BY receipt_date
        """)
        
        db_receipts = cur.fetchall()
        
        print(f"\n📋 RECEIPTS IN DATABASE: {len(db_receipts)} records")
        print("-" * 100)
        print(f"{'ID':<8} {'Date':<12} {'Vendor':<30} {'Amount':>12} {'Invoice':<15}")
        print("-" * 100)
        
        db_invoice_numbers = set()
        total_db_amount = Decimal('0')
        
        for rec_id, date, vendor, desc, amount, source_ref in db_receipts:
            invoice_display = source_ref or '—'
            print(f"{rec_id:<8} {str(date):<12} {vendor[:28]:<30} ${amount:>10,.2f} {invoice_display:<15}")
            total_db_amount += amount or 0
            
            # Extract invoice numbers from source_reference
            if source_ref and source_ref.startswith('FIBRENEW_INVOICE_'):
                inv_num_from_ref = source_ref.replace('FIBRENEW_INVOICE_', '')
                if inv_num_from_ref.isdigit():
                    db_invoice_numbers.add(inv_num_from_ref)
        
        print("-" * 100)
        print(f"{'TOTAL':<50} ${total_db_amount:>10,.2f}")
        
        print("\n" + "="*100)
        print("COMPARISON ANALYSIS")
        print("="*100)
        
        print(f"\nInvoices on statement: {len(statement_invoices)}")
        print(f"Invoices in database: {len(db_invoice_numbers)}")
        
        missing_from_db = statement_invoices - db_invoice_numbers
        extra_in_db = db_invoice_numbers - statement_invoices
        
        if missing_from_db:
            print(f"\n⚠️  MISSING FROM DATABASE: {len(missing_from_db)} invoices")
            print("-" * 100)
            for inv in sorted(missing_from_db, key=int):
                print(f"  Invoice #{inv}")
        else:
            print("\n✓ All statement invoices are in database")
        
        if extra_in_db:
            print(f"\n📌 EXTRA IN DATABASE (not on statement): {len(extra_in_db)} invoices")
            print("-" * 100)
            for inv in sorted(extra_in_db, key=int):
                print(f"  Invoice #{inv}")
        
        # Show invoice number ranges
        if statement_invoices:
            stmt_nums = sorted([int(x) for x in statement_invoices])
            print(f"\nStatement invoice range: #{stmt_nums[0]} - #{stmt_nums[-1]}")
        
        if db_invoice_numbers:
            db_nums = sorted([int(x) for x in db_invoice_numbers])
            print(f"Database invoice range: #{db_nums[0]} - #{db_nums[-1]}")

print("\n" + "="*100)
