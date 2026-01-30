#!/usr/bin/env python3
"""
Final WCB 2012 Reconciliation Summary and Next Steps
"""

import psycopg2
import os
from decimal import Decimal

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("\n" + "="*70)
print("WCB 2012 RECONCILIATION - FINAL STATUS")
print("="*70)

# Current state
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE vendor_name = 'WCB' AND fiscal_year = 2012 AND gross_amount > 0
""")
invoice_count, total_invoices = cur.fetchone()

cur.execute("""
    SELECT COALESCE(SUM(debit_amount), 0)
    FROM banking_transactions
    WHERE transaction_id IN (69282, 69587)
""")
banking_payments = cur.fetchone()[0] or Decimal('0')

cur.execute("""
    SELECT COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE receipt_id IN (145297, 145305) AND vendor_name = 'WCB'
""")
receipt_payments = cur.fetchone()[0] or Decimal('0')

total_payments = banking_payments + receipt_payments
balance = total_invoices - total_payments

print(f"\nCurrent State:")
print(f"  2012 Invoices:  {invoice_count:2} = ${total_invoices:>10,.2f}")
print(f"  Payments:            ${total_payments:>10,.2f}")
print(f"    - Banking:         ${banking_payments:>10,.2f}")
print(f"    - Receipts:        ${receipt_payments:>10,.2f}")
print(f"  Balance:             ${balance:>10,.2f}")
print(f"  Target:              $   3,593.83")
print(f"  Difference:          ${balance - Decimal('3593.83'):>10,.2f}")

# Check linked invoices
print(f"\n{'='*70}")
print("PAYMENT LINKAGE STATUS")
print("="*70)

payments = [
    (145297, "Receipt", "$686.65", "2012-03-19"),
    (69282, "TX", "$3,446.02", "2012-08-28"),
    (69587, "TX", "$553.17", "2012-11-27"),
    (145305, "Receipt", "$593.81", "2012-11-27 (refund)"),
]

for payment_id, ptype, amount, date in payments:
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(r.gross_amount), 0)
        FROM banking_receipt_matching_ledger brml
        JOIN receipts r ON r.receipt_id = brml.receipt_id
        WHERE brml.banking_transaction_id = %s
    """, (payment_id,))
    count, linked_total = cur.fetchone()
    linked_total = linked_total or Decimal('0')
    
    if count > 0:
        status = f"✓ {count} linked = ${linked_total:,.2f}"
    else:
        status = "✗ No links"
    
    print(f"{ptype:7} {payment_id:6} {amount:>12} ({date:12}) | {status}")

# Show unlinked invoices
print(f"\n{'='*70}")
print("UNLINKED INVOICES (2012)")
print("="*70)

cur.execute("""
    SELECT r.receipt_id, r.source_reference, r.invoice_date, r.gross_amount, 
           r.sub_classification, r.description
    FROM receipts r
    WHERE r.vendor_name = 'WCB'
      AND r.fiscal_year = 2012
      AND r.gross_amount > 0
      AND NOT EXISTS (
          SELECT 1 FROM banking_receipt_matching_ledger brml
          WHERE brml.receipt_id = r.receipt_id
      )
    ORDER BY r.invoice_date
""")

unlinked = cur.fetchall()
unlinked_total = Decimal('0')

for receipt_id, ref, date, amount, subcat, desc in unlinked:
    subcat_display = subcat or "WCB"
    desc_display = (desc[:35] + "...") if desc and len(desc) > 35 else (desc or "")
    print(f"  {receipt_id:6} | {date} | ${amount:>10,.2f} | {subcat_display:20} | {desc_display}")
    unlinked_total += amount

print(f"\n  Total Unlinked: {len(unlinked)} = ${unlinked_total:,.2f}")

print(f"\n{'='*70}")
print("COMPLETED IMPROVEMENTS")
print("="*70)

print("""
✅ Schema Enhancements Applied:
   - fiscal_year column (separates 2011 from 2012)
   - invoice_date, due_date, period_start, period_end
   - amount_allocated in ledger (tracks partial payments)
   - Indexes for performance

✅ Vendor Standardization:
   - WCB ALBERTA → WCB (3 records)
   - Subcategories: 'WCB' and 'WCB-fees/penalties'

✅ Code Fixes:
   - Desktop app now creates ledger entries (prevents crash)
   - Bulk linking tool created (bulk_link_invoices.py)

✅ Data Cleanup:
   - Receipt 145296 (2011-12-30) marked as fiscal_year 2011
   - Invoice 18714897 restored and linked to TX 69587
""")

print(f"\n{'='*70}")
print("REMAINING WORK")
print("="*70)

print(f"""
1. Link remaining {len(unlinked)} invoices to payments
   - Receipt 145297 ($686.65): Should this link to itself?
     (It's both a payment AND an invoice - same record)
   
2. Investigate $1,854 balance discrepancy:
   - Database shows ${balance:,.2f}
   - Excel shows $3,593.83
   - Difference: ${balance - Decimal('3593.83'):,.2f}
   
   Possible causes:
   - Additional invoices in Excel not yet in database
   - Different interpretation of what's included in 2012
   - Receipt 145297 double-counting issue

3. Schema consideration:
   - receipts.banking_transaction_id can't link to other receipts
   - Need alternate approach for receipt-to-receipt links
   - Consider: separate 'receipt_payment_links' table
""")

print(f"\n{'='*70}")
print("NEXT SESSION: Start with bulk_link_invoices.py --list-unlinked --vendor WCB --fiscal-year 2012")
print("="*70)

conn.close()
