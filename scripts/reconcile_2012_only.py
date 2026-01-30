#!/usr/bin/env python3
"""
2012 WCB Account Reconciliation (excluding 2011 prior-year settlement)
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
print("2012 WCB ACCOUNT RECONCILIATION")
print("(Excluding 2011-12-30 prior-year settlement TX 145296)")
print("="*70)

# Get all 2012 WCB invoices (excluding 2011-12-30)
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE vendor_name IN ('WCB', 'WCB ALBERTA')
      AND gross_amount > 0
      AND receipt_date >= '2012-01-01'
""")
invoice_count, total_invoices = cur.fetchone()
total_invoices = total_invoices or Decimal('0')

print(f"\n2012 INVOICES (dated 2012-01-01 or later):")
print(f"  Count: {invoice_count}")
print(f"  Total: ${total_invoices:,.2f}")

# Detail by vendor
cur.execute("""
    SELECT vendor_name, COUNT(*), COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE vendor_name IN ('WCB', 'WCB ALBERTA')
      AND gross_amount > 0
      AND receipt_date >= '2012-01-01'
    GROUP BY vendor_name
    ORDER BY vendor_name
""")

for vendor, count, amount in cur.fetchall():
    print(f"    {vendor}: {count} invoices = ${amount:,.2f}")

# Get all 2012 payments
print(f"\n2012 PAYMENTS:")

payment_details = {
    145297: ("Receipt", "2012-03-19", "installment"),
    69282: ("TX", "2012-08-28", "WCB payment"),
    69587: ("TX", "2012-11-27", "wcb payment"),
    145305: ("Receipt", "2012-11-27", "waived fee - refund"),
}

total_payments = Decimal('0')

for payment_id, (payment_type, date, desc) in payment_details.items():
    if payment_type == "Receipt":
        cur.execute("SELECT gross_amount FROM receipts WHERE receipt_id = %s", (payment_id,))
    else:
        cur.execute("SELECT debit_amount FROM banking_transactions WHERE transaction_id = %s", (payment_id,))
    
    row = cur.fetchone()
    if row:
        amount = row[0] or Decimal('0')
        total_payments += amount
        status = "✓"
    else:
        amount = Decimal('0')
        status = "✗"
    
    print(f"  {status} {payment_type:7} {payment_id:6} ({date}): ${amount:>10,.2f}")

print(f"\n  TOTAL PAYMENTS: ${total_payments:,.2f}")

# Calculate final balance
final_balance = total_invoices - total_payments

print(f"\n{'='*70}")
print(f"FINAL BALANCE CALCULATION:")
print(f"  Invoices:      ${total_invoices:>12,.2f}")
print(f"- Payments:      ${total_payments:>12,.2f}")
print(f"= Balance:       ${final_balance:>12,.2f}")
print(f"{'='*70}")
print(f"TARGET (Excel):  ${Decimal('3593.83'):>12,.2f}")

diff = final_balance - Decimal('3593.83')
if abs(diff) < Decimal('0.01'):
    print(f"\n✅ PERFECT MATCH!")
else:
    print(f"Difference:      ${diff:>12,.2f}")

# Now show which invoices should be linked to 145297
print(f"\n{'='*70}")
print("INVOICES BEFORE FIRST PAYMENT (2012-03-19)")
print("(Should be linked to Receipt 145297 - $686.65)")
print(f"{'='*70}\n")

cur.execute("""
    SELECT receipt_id, source_reference, receipt_date, gross_amount, vendor_name
    FROM receipts
    WHERE vendor_name IN ('WCB', 'WCB ALBERTA')
      AND gross_amount > 0
      AND receipt_date >= '2012-01-01'
      AND receipt_date < '2012-03-19'
    ORDER BY receipt_date, vendor_name
""")

total_before = Decimal('0')
for receipt_id, ref, date, amount, vendor in cur.fetchall():
    print(f"  Receipt {receipt_id:6} ({date}) | Ref {ref:12} | ${amount:>10,.2f} | {vendor}")
    total_before += amount

print(f"\n  TOTAL: ${total_before:,.2f}")
print(f"  Payment 145297: $686.65")

if abs(total_before - Decimal('686.65')) < Decimal('0.01'):
    print(f"\n  ✅ PERFECT MATCH - Link all these to Receipt 145297")
else:
    diff = total_before - Decimal('686.65')
    print(f"\n  ⚠️  DIFFERENCE: ${diff:+,.2f}")

conn.close()
