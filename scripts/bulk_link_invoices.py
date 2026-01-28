#!/usr/bin/env python3
"""
Bulk Invoice-to-Payment Linking Tool

Usage:
  python bulk_link_invoices.py --payment 69282 --invoices 145293,145291,145292
  python bulk_link_invoices.py --payment 145297 --invoices 145293,145291 --type receipt
  python bulk_link_invoices.py --list-unlinked --vendor WCB
"""

import psycopg2
import os
import argparse
from decimal import Decimal
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def list_unlinked_invoices(vendor=None, fiscal_year=None):
    """Show all unlinked invoices for a vendor"""
    conn = get_connection()
    cur = conn.cursor()
    
    where_clauses = ["r.gross_amount > 0"]
    params = []
    
    if vendor:
        where_clauses.append("r.vendor_name = %s")
        params.append(vendor)
    
    if fiscal_year:
        where_clauses.append("r.fiscal_year = %s")
        params.append(fiscal_year)
    
    where_clauses.append("""
        NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger brml
            WHERE brml.receipt_id = r.receipt_id
        )
    """)
    
    query = f"""
        SELECT r.receipt_id, r.source_reference, r.invoice_date, r.gross_amount, 
               r.description, r.vendor_name
        FROM receipts r
        WHERE {' AND '.join(where_clauses)}
        ORDER BY r.invoice_date, r.receipt_id
    """
    
    cur.execute(query, params)
    rows = cur.fetchall()
    
    print(f"\n{'='*70}")
    print(f"UNLINKED INVOICES")
    if vendor:
        print(f"Vendor: {vendor}")
    if fiscal_year:
        print(f"Fiscal Year: {fiscal_year}")
    print(f"{'='*70}\n")
    
    if not rows:
        print("  No unlinked invoices found.")
    else:
        total = Decimal('0')
        for receipt_id, ref, date, amount, desc, vendor_name in rows:
            ref_display = ref if ref else "N/A"
            desc_display = (desc[:40] + "...") if desc and len(desc) > 40 else (desc or "")
            print(f"  {receipt_id:6} | {date} | ${amount:>10,.2f} | {ref_display:15} | {desc_display}")
            total += amount
        
        print(f"\n  Total: {len(rows)} invoices = ${total:,.2f}")
    
    conn.close()

def get_payment_info(payment_id, payment_type='banking'):
    """Get payment details"""
    conn = get_connection()
    cur = conn.cursor()
    
    if payment_type == 'banking':
        cur.execute("""
            SELECT transaction_id, description, debit_amount, transaction_date
            FROM banking_transactions
            WHERE transaction_id = %s
        """, (payment_id,))
        row = cur.fetchone()
        if row:
            amount = row[2] or Decimal('0')
            date = row[3]
            desc = row[1]
        else:
            conn.close()
            return None
    else:  # receipt
        cur.execute("""
            SELECT receipt_id, description, gross_amount, receipt_date
            FROM receipts
            WHERE receipt_id = %s
        """, (payment_id,))
        row = cur.fetchone()
        if row:
            amount = row[2] or Decimal('0')
            date = row[3]
            desc = row[1]
        else:
            conn.close()
            return None
    
    # Get already allocated amount
    cur.execute("""
        SELECT COALESCE(SUM(amount_allocated), 0)
        FROM banking_receipt_matching_ledger
        WHERE banking_transaction_id = %s
    """, (payment_id,))
    allocated = cur.fetchone()[0] or Decimal('0')
    
    conn.close()
    return {
        'id': payment_id,
        'amount': amount,
        'date': date,
        'description': desc,
        'allocated': allocated,
        'available': amount - allocated
    }

def link_invoices_to_payment(payment_id, invoice_ids, payment_type='banking', dry_run=True):
    """Link multiple invoices to a payment"""
    conn = get_connection()
    cur = conn.cursor()
    
    # Get payment info
    payment = get_payment_info(payment_id, payment_type)
    if not payment:
        print(f"❌ Payment {payment_id} not found")
        conn.close()
        return
    
    print(f"\n{'='*70}")
    print(f"BULK LINKING: {len(invoice_ids)} invoices to payment {payment_id}")
    print(f"{'='*70}")
    print(f"\nPayment Details:")
    print(f"  ID: {payment['id']}")
    print(f"  Amount: ${payment['amount']:,.2f}")
    print(f"  Date: {payment['date']}")
    print(f"  Description: {payment['description']}")
    print(f"  Already Allocated: ${payment['allocated']:,.2f}")
    print(f"  Available: ${payment['available']:,.2f}")
    
    # Get invoice details
    placeholders = ','.join(['%s'] * len(invoice_ids))
    cur.execute(f"""
        SELECT receipt_id, source_reference, invoice_date, gross_amount, description
        FROM receipts
        WHERE receipt_id IN ({placeholders})
        ORDER BY invoice_date
    """, invoice_ids)
    
    invoices = cur.fetchall()
    
    if len(invoices) != len(invoice_ids):
        print(f"\n❌ Warning: Found {len(invoices)} invoices but {len(invoice_ids)} were requested")
        missing = set(invoice_ids) - {r[0] for r in invoices}
        print(f"   Missing IDs: {missing}")
    
    print(f"\nInvoices to Link:")
    total_to_link = Decimal('0')
    for receipt_id, ref, date, amount, desc in invoices:
        desc_display = (desc[:30] + "...") if desc and len(desc) > 30 else (desc or "")
        print(f"  {receipt_id:6} | {date} | ${amount:>10,.2f} | {desc_display}")
        total_to_link += amount
    
    print(f"\n  Total Invoice Amount: ${total_to_link:,.2f}")
    print(f"  Payment Available:    ${payment['available']:,.2f}")
    
    difference = payment['available'] - total_to_link
    if abs(difference) < Decimal('0.01'):
        print(f"  ✅ PERFECT MATCH!")
    elif difference > 0:
        print(f"  ⚠️  UNDER-ALLOCATED: ${difference:,.2f} remaining")
    else:
        print(f"  ❌ OVER-ALLOCATED: ${-difference:,.2f} over payment amount!")
        if not dry_run:
            print("\n❌ Cannot proceed - would over-allocate payment")
            conn.close()
            return
    
    if dry_run:
        print(f"\n{'='*70}")
        print("DRY RUN - No changes made")
        print("Run with --write to apply changes")
        print(f"{'='*70}")
        conn.close()
        return
    
    # Apply the links
    print(f"\n{'='*70}")
    print("APPLYING LINKS...")
    print(f"{'='*70}")
    
    try:
        for receipt_id, ref, date, amount, desc in invoices:
            # Update receipt banking_transaction_id
            cur.execute("""
                UPDATE receipts
                SET banking_transaction_id = %s
                WHERE receipt_id = %s
            """, (payment_id, receipt_id))
            
            # Create or update ledger entry
            cur.execute("""
                INSERT INTO banking_receipt_matching_ledger 
                (banking_transaction_id, receipt_id, amount_allocated, allocation_date, allocation_type, created_by)
                VALUES (%s, %s, %s, NOW(), 'payment', %s)
                ON CONFLICT (banking_transaction_id, receipt_id) 
                DO UPDATE SET 
                    amount_allocated = EXCLUDED.amount_allocated,
                    allocation_date = NOW()
            """, (payment_id, receipt_id, amount, 'bulk_link_tool'))
            
            print(f"  ✓ Linked {receipt_id} (${amount:,.2f})")
        
        conn.commit()
        print(f"\n✅ Successfully linked {len(invoices)} invoices")
        print(f"   Total allocated: ${total_to_link:,.2f}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description='Bulk Invoice-to-Payment Linking Tool')
    parser.add_argument('--payment', type=int, help='Payment ID (banking transaction or receipt)')
    parser.add_argument('--invoices', type=str, help='Comma-separated invoice IDs')
    parser.add_argument('--type', choices=['banking', 'receipt'], default='banking', 
                       help='Payment type (default: banking)')
    parser.add_argument('--list-unlinked', action='store_true', 
                       help='List all unlinked invoices')
    parser.add_argument('--vendor', type=str, help='Filter by vendor')
    parser.add_argument('--fiscal-year', type=int, help='Filter by fiscal year')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    
    args = parser.parse_args()
    
    if args.list_unlinked:
        list_unlinked_invoices(vendor=args.vendor, fiscal_year=args.fiscal_year)
    elif args.payment and args.invoices:
        invoice_ids = [int(x.strip()) for x in args.invoices.split(',')]
        link_invoices_to_payment(args.payment, invoice_ids, args.type, dry_run=not args.write)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
