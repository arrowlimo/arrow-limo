#!/usr/bin/env python3
"""
Final WCB Account Reconciliation Summary
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
print("WCB ACCOUNT FINAL RECONCILIATION")
print("="*70)

# Get all WCB-related invoices
cur.execute("""
    SELECT COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE vendor_name IN ('WCB', 'WCB ALBERTA')
      AND gross_amount > 0
""")
total_invoices = cur.fetchone()[0] or Decimal('0')

# Get all WCB receipts (payment receipts)
cur.execute("""
    SELECT COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE vendor_name = 'WCB'
      AND gross_amount > 0
      AND receipt_id IN (145297, 145305)
""")
receipt_payments = cur.fetchone()[0] or Decimal('0')

# Get all WCB banking transactions (debits = payments out)
cur.execute("""
    SELECT COALESCE(SUM(debit_amount), 0)
    FROM banking_transactions
    WHERE transaction_id IN (69282, 69587)
""")
banking_payments = cur.fetchone()[0] or Decimal('0')

total_payments = receipt_payments + banking_payments

print(f"\nOPENING BALANCE (2011-01-01): $0.00")
print(f"\nINVOICES (amounts owed to WCB):")
print(f"  WCB invoices: {total_invoices:>20,.2f}")
cur.execute("""
    SELECT vendor_name, COUNT(*), COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE vendor_name IN ('WCB', 'WCB ALBERTA') AND gross_amount > 0
    GROUP BY vendor_name
""")
for vendor, count, amount in cur.fetchall():
    print(f"    {vendor}: {count:2} invoices = ${amount:>20,.2f}")

print(f"\nPAYMENTS (amounts paid to WCB):")
print(f"  Receipt 145297 (2012-03-19): ${receipt_payments:>20,.2f}")
print(f"  TX 69282 (2012-08-28):      ${banking_payments:>20,.2f}")

cur.execute("""
    SELECT COALESCE(SUM(debit_amount), 0)
    FROM banking_transactions
    WHERE transaction_id = 69282
""")
tx69282 = cur.fetchone()[0] or Decimal('0')

cur.execute("""
    SELECT COALESCE(SUM(debit_amount), 0)
    FROM banking_transactions
    WHERE transaction_id = 69587
""")
tx69587 = cur.fetchone()[0] or Decimal('0')

print(f"    (includes invoice 145308: $553.17)")
print(f"  TX 69587 (2012-11-27):      ${tx69587:>20,.2f}")
print(f"  Receipt 145305 (2012-11-27) [REFUND - waived fee]: ${Decimal('593.81'):>20,.2f}")

print(f"\n  TOTAL PAID:")
print(f"    Receipt payments: ${receipt_payments:>20,.2f}")
print(f"    Banking payments: ${banking_payments:>20,.2f}")
print(f"    Total: ${total_payments:>24,.2f}")

final_balance = total_invoices - total_payments

print(f"\n{'='*70}")
print(f"FINAL BALANCE (outstanding payable): ${final_balance:>20,.2f}")
print(f"TARGET BALANCE (from Excel):         $           3,593.83")
print(f"{'='*70}")

if abs(final_balance - Decimal('3593.83')) < Decimal('0.01'):
    print("\n✅ ACCOUNT RECONCILED! Balance matches Excel data.")
else:
    diff = final_balance - Decimal('3593.83')
    print(f"\n⚠️  DIFFERENCE: ${diff:+,.2f}")
    print("\nThis difference may be due to:")
    print("  - Invoices not yet imported from LMS")
    print("  - Payments recorded differently in two systems")
    print("  - Data entry errors in either system")

# Final detailed payment linkage status
print(f"\n{'='*70}")
print("PAYMENT LINKAGE STATUS")
print(f"{'='*70}")

payments_summary = [
    (145297, "Receipt", "$686.65"),
    (69282, "TX", "$3,446.02"),
    (69587, "TX", "$553.17"),
    (145305, "Receipt", "$593.81 (refund)"),
]

for payment_id, payment_type, amount in payments_summary:
    if payment_type == "Receipt":
        cur.execute("""
            SELECT COUNT(*), COALESCE(SUM(r.gross_amount), 0)
            FROM banking_receipt_matching_ledger brml
            JOIN receipts r ON r.receipt_id = brml.receipt_id
            WHERE brml.banking_transaction_id = %s
        """, (payment_id,))
    else:
        cur.execute("""
            SELECT COUNT(*), COALESCE(SUM(r.gross_amount), 0)
            FROM banking_receipt_matching_ledger brml
            JOIN receipts r ON r.receipt_id = brml.receipt_id
            WHERE brml.banking_transaction_id = %s
        """, (payment_id,))
    
    count, total = cur.fetchone()
    total = total or Decimal('0')
    
    if count > 0:
        status = f"✓ {count} invoice(s) linked = ${total:,.2f}"
    else:
        status = f"✗ No invoices linked"
    
    print(f"{payment_type} {payment_id:6} {amount:>15} | {status}")

conn.close()
