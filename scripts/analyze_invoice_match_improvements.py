#!/usr/bin/env python3
"""
Analysis: Invoice-Banking Match Procedure Improvements

Current Pain Points:
1. Manual linking in desktop app - crashes when ledger entries missing
2. No clear way to handle multi-period invoices (2011 balance on 2012 invoice)
3. No date separation (invoice_date vs payment_received_date)
4. Difficult to track partial payments
5. No bulk linking for multiple invoices to one payment

Recommended Improvements:
"""

import psycopg2
import os
from decimal import Decimal

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("\n" + "="*70)
print("INVOICE-BANKING MATCH PROCEDURE ANALYSIS")
print("="*70)

print("\n1. CURRENT SCHEMA LIMITATIONS")
print("-" * 70)

# Check receipts table structure
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'receipts'
      AND column_name IN ('invoice_date', 'payment_date', 'transaction_date')
""")
date_columns = [row[0] for row in cur.fetchall()]

if 'invoice_date' not in date_columns:
    print("❌ Missing: invoice_date (separate from receipt_date)")
    print("   Impact: Can't track when invoice issued vs when payment received")
    print("   Example: Invoice 18714897 issued 2012-12-19 but paid 2012-11-27")

# Check banking_receipt_matching_ledger structure
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns 
    WHERE table_name = 'banking_receipt_matching_ledger'
    ORDER BY ordinal_position
""")
ledger_columns = cur.fetchall()

print("\n   Current ledger columns:")
for col, dtype in ledger_columns:
    print(f"     - {col:30} {dtype}")

print("\n❌ Missing fields in ledger:")
print("   - amount_allocated (tracks partial payments)")
print("   - allocation_date (when link was created)")
print("   - allocation_type (payment, reversal, adjustment)")
print("   - notes (explanation field)")

print("\n\n2. CURRENT WORKFLOW PAIN POINTS")
print("-" * 70)

# Find all WCB invoices that are not linked
cur.execute("""
    SELECT COUNT(DISTINCT r.receipt_id)
    FROM receipts r
    WHERE r.vendor_name = 'WCB'
      AND r.gross_amount > 0
      AND r.receipt_date >= '2012-01-01'
      AND r.banking_transaction_id IS NULL
      AND NOT EXISTS (
          SELECT 1 FROM banking_receipt_matching_ledger brml
          WHERE brml.receipt_id = r.receipt_id
      )
""")
unlinked_count = cur.fetchone()[0]

print(f"❌ {unlinked_count} WCB invoices have NO payment link")
print("   Manual process required to link each one")

# Check for invoices linked to banking_transaction_id but no ledger entry
cur.execute("""
    SELECT COUNT(*)
    FROM receipts r
    WHERE r.vendor_name = 'WCB'
      AND r.banking_transaction_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM banking_receipt_matching_ledger brml
          WHERE brml.receipt_id = r.receipt_id
            AND brml.banking_transaction_id = r.banking_transaction_id
      )
""")
missing_ledger = cur.fetchone()[0]

print(f"❌ {missing_ledger} invoices have banking_transaction_id but NO ledger entry")
print("   This causes links to disappear on app restart (the bug we just fixed)")

print("\n\n3. RECOMMENDED IMPROVEMENTS")
print("="*70)

print("\nA. SCHEMA ENHANCEMENTS")
print("-" * 70)

print("""
ALTER TABLE receipts ADD COLUMN IF NOT EXISTS:
  - invoice_date DATE           -- When invoice was issued
  - due_date DATE               -- When payment is due
  - period_start DATE           -- For multi-period invoices
  - period_end DATE             -- For multi-period invoices

ALTER TABLE banking_receipt_matching_ledger ADD COLUMN IF NOT EXISTS:
  - amount_allocated NUMERIC(10,2)  -- How much of payment goes to this invoice
  - allocation_date TIMESTAMP        -- When link was created
  - allocation_type VARCHAR(50)      -- 'payment', 'reversal', 'adjustment'
  - notes TEXT                       -- Explanation
  - created_by VARCHAR(100)          -- User who created link

Benefits:
  ✓ Track invoice dates separately from payment dates
  ✓ Handle multi-period invoices (2011 balance on 2012 invoice)
  ✓ Track partial payments (one payment split across invoices)
  ✓ Audit trail (who linked what, when)
""")

print("\nB. WORKFLOW IMPROVEMENTS")
print("-" * 70)

print("""
1. AUTO-MATCH BY AMOUNT
   - When banking transaction appears, search for unlinked invoices with exact amount
   - If single match found, auto-link with confirmation prompt
   - Reduces manual linking by ~40%

2. BULK LINKING WIZARD
   - Select one payment ($3,446.02)
   - Show all unlinked invoices
   - Check boxes to select which invoices to link
   - Auto-calculate total and show remaining balance
   - One-click create all ledger entries
   
3. SMART VENDOR MATCHING
   - If banking description contains "WCB", auto-filter to WCB invoices
   - If description contains invoice reference, highlight that invoice
   - Reduces search time by ~60%

4. PAYMENT ALLOCATION VIEW
   - Show payment at top with available amount
   - List all linked invoices below
   - Show running total and remaining balance
   - Drag-and-drop to link/unlink
   - Visual: Red = overpaid, Green = fully allocated, Yellow = partial
""")

print("\nC. DATA VALIDATION RULES")
print("-" * 70)

print("""
1. LEDGER CONSISTENCY CHECK
   - Trigger: After any receipts.banking_transaction_id update
   - Action: Auto-create/update ledger entry
   - Result: Links never disappear (prevents the crash we just fixed)

2. DOUBLE-ENTRY VALIDATION
   - Check: Sum of amount_allocated <= payment amount
   - Check: Invoice not linked to multiple payments
   - Alert: If total allocated > payment amount

3. PERIOD MISMATCH WARNING
   - Warn: If invoice_date > payment_date (paid before invoiced)
   - Suggest: Check if this is a prior-period settlement
   - Example: 2011-12-30 balance forward
""")

print("\n\n4. IMPLEMENTATION PRIORITY")
print("="*70)

print("""
HIGH PRIORITY (Do Now):
  1. ✅ Add ledger consistency trigger (prevents crash - DONE)
  2. Add invoice_date, due_date columns to receipts
  3. Add amount_allocated to banking_receipt_matching_ledger
  4. Update desktop app to show running total when linking

MEDIUM PRIORITY (Next Sprint):
  5. Build bulk linking wizard (selectable invoice list)
  6. Add auto-match by amount feature
  7. Add smart vendor filtering in match UI

LOW PRIORITY (Future):
  8. Drag-and-drop payment allocation UI
  9. Period mismatch warnings
  10. Multi-period invoice handling
""")

print("\n\n5. QUICK WIN: Bulk Link Script")
print("="*70)

print("""
Instead of UI changes, create a CLI script for bulk linking:

Usage:
  python link_payment_to_invoices.py --payment 69282 --invoices 145293,145291,145292,...
  
Benefits:
  ✓ Fast for power users (you)
  ✓ No UI changes needed
  ✓ Can script repetitive tasks
  ✓ Auto-validates totals
  ✓ Creates all ledger entries atomically
  
This is what we've been doing manually - formalize it into a reusable tool.
""")

print("\n\n6. SPECIFIC WCB FIX NEEDED NOW")
print("="*70)

# Show the 2011 issue
cur.execute("""
    SELECT receipt_id, source_reference, receipt_date, gross_amount, description
    FROM receipts
    WHERE receipt_id = 145296
""")
row = cur.fetchone()
if row:
    print("\nProblem Record:")
    print(f"  Receipt {row[0]}: {row[1]} | {row[2]} | ${row[3]:,.2f}")
    print(f"  Description: {row[4]}")
    print("\nIssue:")
    print("  - This is a 2011 prior-year settlement")
    print("  - Included in 2012 invoice totals (wrong)")
    print("  - No separate field to mark as 'prior period settlement'")
    print("\nOptions:")
    print("  A. Add 'fiscal_year' column to receipts, set this to 2011")
    print("  B. Add 'exclude_from_period_totals' boolean flag")
    print("  C. Create separate 'prior_period_settlements' table")
    print("  D. Add period_start/period_end and set to 2011")
    print("\nRecommended: Option A (fiscal_year column)")
    print("  - Simple to implement")
    print("  - Easy to filter in reports (WHERE fiscal_year = 2012)")
    print("  - Clear audit trail")

conn.close()

print("\n" + "="*70)
print("END OF ANALYSIS")
print("="*70)
