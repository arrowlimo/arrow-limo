#!/usr/bin/env python
"""
FIFO Payment Allocation Engine
Applies payments to oldest unpaid invoices first, chronologically

Use case: You have:
- Historical invoices (e.g., Fibrenew 2013-2014)
- Payment transactions (checks, cash)
- Need to allocate payments to invoices in date order
- Track $14,000 outstanding balance
"""

import psycopg2
from datetime import datetime
from decimal import Decimal
from collections import defaultdict

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = '***REMOVED***'


class FIFOPaymentAllocator:
    """Allocate payments to invoices using FIFO (oldest first)"""
    
    def __init__(self, vendor_name=None, dry_run=True):
        self.vendor_name = vendor_name
        self.dry_run = dry_run
        self.conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
        )
        
    def allocate_by_vendor(self, vendor_pattern):
        """Allocate all payments for a specific vendor"""
        print("=" * 80)
        print(f"FIFO PAYMENT ALLOCATION: {vendor_pattern}")
        print("=" * 80)
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}\n")
        
        # Step 1: Get all invoices/receipts for vendor (oldest first)
        invoices = self.get_vendor_invoices(vendor_pattern)
        print(f"Step 1: Found {len(invoices)} invoices for {vendor_pattern}")
        
        # Step 2: Get all payments for vendor (chronologically)
        payments = self.get_vendor_payments(vendor_pattern)
        print(f"Step 2: Found {len(payments)} payments for {vendor_pattern}")
        
        # Step 3: Apply FIFO allocation
        print(f"\nStep 3: Applying FIFO allocation...\n")
        allocations = self.apply_fifo_allocation(invoices, payments)
        
        # Step 4: Report results
        self.generate_allocation_report(invoices, payments, allocations)
        
        # Step 5: Apply to database (if not dry run)
        if not self.dry_run and allocations:
            self.save_allocations(allocations)
            
        return allocations
        
    def get_vendor_invoices(self, vendor_pattern):
        """Get all invoices/receipts for vendor, sorted by date (oldest first)"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT 
                receipt_id,
                receipt_date,
                vendor_name,
                gross_amount,
                description,
                source_reference,
                banking_transaction_id
            FROM receipts
            WHERE vendor_name ILIKE %s
                AND gross_amount > 0
            ORDER BY receipt_date ASC, receipt_id ASC
        """, (f"%{vendor_pattern}%",))
        
        invoices = []
        for row in cur.fetchall():
            invoices.append({
                'receipt_id': row[0],
                'date': row[1],
                'vendor': row[2],
                'amount': float(row[3]),
                'description': row[4],
                'invoice_num': row[5],
                'banking_id': row[6],
                'paid_amount': 0.0,  # Will be calculated
                'balance': float(row[3])  # Initially unpaid
            })
        
        cur.close()
        return invoices
        
    def get_vendor_payments(self, vendor_pattern):
        """Get all banking payments for vendor, chronologically"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT 
                transaction_id,
                transaction_date,
                description,
                debit_amount,
                check_number
            FROM banking_transactions
            WHERE description ILIKE %s
                AND debit_amount > 0
            ORDER BY transaction_date ASC, transaction_id ASC
        """, (f"%{vendor_pattern}%",))
        
        payments = []
        for row in cur.fetchall():
            payments.append({
                'transaction_id': row[0],
                'date': row[1],
                'description': row[2],
                'amount': float(row[3]),
                'check_number': row[4],
                'allocated': 0.0,  # Amount already allocated
                'remaining': float(row[3])  # Amount still available
            })
        
        cur.close()
        return payments
        
    def apply_fifo_allocation(self, invoices, payments):
        """Apply payments to invoices using FIFO"""
        allocations = []  # List of (invoice_id, payment_id, amount) tuples
        
        payment_idx = 0
        
        for invoice in invoices:
            if payment_idx >= len(payments):
                print(f"  ⚠️  No more payments available for Invoice {invoice['invoice_num'] or invoice['receipt_id']}")
                break
                
            invoice_balance = invoice['amount']
            
            # Apply payments to this invoice until fully paid
            while invoice_balance > 0.01 and payment_idx < len(payments):
                payment = payments[payment_idx]
                
                # How much can we allocate from this payment?
                allocate_amount = min(invoice_balance, payment['remaining'])
                
                if allocate_amount > 0.01:
                    allocations.append({
                        'receipt_id': invoice['receipt_id'],
                        'banking_id': payment['transaction_id'],
                        'amount': allocate_amount,
                        'invoice_num': invoice['invoice_num'] or f"Receipt {invoice['receipt_id']}",
                        'invoice_date': invoice['date'],
                        'invoice_total': invoice['amount'],
                        'payment_date': payment['date'],
                        'payment_total': payment['amount'],
                        'check_number': payment['check_number']
                    })
                    
                    # Update tracking
                    invoice_balance -= allocate_amount
                    payment['remaining'] -= allocate_amount
                    payment['allocated'] += allocate_amount
                    invoice['paid_amount'] += allocate_amount
                    invoice['balance'] = invoice_balance
                    
                    print(f"  ✅ Invoice {invoice['invoice_num'] or invoice['receipt_id']} "
                          f"({invoice['date']}) ${allocate_amount:,.2f} ← "
                          f"Payment {payment['transaction_id']} ({payment['date']})")
                
                # If payment fully used, move to next payment
                if payment['remaining'] < 0.01:
                    payment_idx += 1
                    
            # Mark invoice status
            if invoice_balance < 0.01:
                invoice['status'] = 'PAID'
            else:
                invoice['status'] = 'PARTIAL' if invoice['paid_amount'] > 0 else 'UNPAID'
                
        return allocations
        
    def generate_allocation_report(self, invoices, payments, allocations):
        """Generate detailed allocation report"""
        print("\n" + "=" * 80)
        print("ALLOCATION REPORT")
        print("=" * 80)
        
        # Invoice summary
        print(f"\n📋 INVOICES:")
        total_invoiced = sum(inv['amount'] for inv in invoices)
        total_paid = sum(inv['paid_amount'] for inv in invoices)
        total_outstanding = total_invoiced - total_paid
        
        paid_count = len([i for i in invoices if i['status'] == 'PAID'])
        partial_count = len([i for i in invoices if i['status'] == 'PARTIAL'])
        unpaid_count = len([i for i in invoices if i['status'] == 'UNPAID'])
        
        print(f"  Total Invoices: {len(invoices)}")
        print(f"  Paid: {paid_count} | Partial: {partial_count} | Unpaid: {unpaid_count}")
        print(f"  Total Invoiced: ${total_invoiced:,.2f}")
        print(f"  Total Paid: ${total_paid:,.2f}")
        print(f"  Outstanding: ${total_outstanding:,.2f}")
        
        # Payment summary
        print(f"\n💰 PAYMENTS:")
        total_payments = sum(pmt['amount'] for pmt in payments)
        total_allocated = sum(pmt['allocated'] for pmt in payments)
        total_unallocated = total_payments - total_allocated
        
        print(f"  Total Payments: {len(payments)}")
        print(f"  Total Payment Amount: ${total_payments:,.2f}")
        print(f"  Allocated: ${total_allocated:,.2f}")
        print(f"  Unallocated: ${total_unallocated:,.2f}")
        
        # Unpaid invoices
        unpaid_invoices = [i for i in invoices if i['balance'] > 0.01]
        if unpaid_invoices:
            print(f"\n❌ UNPAID/PARTIAL INVOICES ({len(unpaid_invoices)}):")
            for inv in unpaid_invoices[:10]:  # Show first 10
                status = "PARTIAL" if inv['paid_amount'] > 0 else "UNPAID"
                print(f"  {inv['date']} | Invoice {inv['invoice_num'] or inv['receipt_id']} | "
                      f"${inv['amount']:,.2f} | Paid: ${inv['paid_amount']:,.2f} | "
                      f"Balance: ${inv['balance']:,.2f} | {status}")
            if len(unpaid_invoices) > 10:
                print(f"  ... and {len(unpaid_invoices) - 10} more")
        
        # Excess payments
        unallocated_payments = [p for p in payments if p['remaining'] > 0.01]
        if unallocated_payments:
            print(f"\n💵 UNALLOCATED PAYMENTS ({len(unallocated_payments)}):")
            for pmt in unallocated_payments[:10]:
                print(f"  {pmt['date']} | Check {pmt['check_number'] or 'N/A'} | "
                      f"${pmt['amount']:,.2f} | Allocated: ${pmt['allocated']:,.2f} | "
                      f"Remaining: ${pmt['remaining']:,.2f}")
                      
    def save_allocations(self, allocations):
        """Save allocations to database"""
        print("\n" + "=" * 80)
        print("SAVING ALLOCATIONS TO DATABASE")
        print("=" * 80)
        
        cur = self.conn.cursor()
        saved = 0
        
        for alloc in allocations:
            try:
                # Link receipt to banking transaction
                cur.execute("""
                    UPDATE receipts
                    SET banking_transaction_id = %s
                    WHERE receipt_id = %s
                """, (alloc['banking_id'], alloc['receipt_id']))
                saved += 1
            except Exception as e:
                print(f"  ❌ Error saving allocation: {e}")
                
        self.conn.commit()
        cur.close()
        
        print(f"\n✅ Saved {saved} allocations")
        
    def close(self):
        """Close database connection"""
        self.conn.close()


if __name__ == "__main__":
    import sys
    
    # Get vendor from command line or default to Fibrenew
    vendor = sys.argv[1] if len(sys.argv) > 1 else "fibrenew"
    
    # Check for --apply flag
    dry_run = '--apply' not in sys.argv
    
    if not dry_run:
        print("⚠️  LIVE MODE - Will update database")
        response = input("Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled")
            sys.exit(0)
    
    allocator = FIFOPaymentAllocator(dry_run=dry_run)
    allocations = allocator.allocate_by_vendor(vendor)
    allocator.close()
    
    print("\n" + "=" * 80)
    if dry_run:
        print("DRY RUN COMPLETE - No changes made")
        print(f"To apply: python {sys.argv[0]} {vendor} --apply")
    else:
        print("ALLOCATION COMPLETE")
    print("=" * 80)
