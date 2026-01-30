#!/usr/bin/env python3
"""
Check if 2012 WCB account has $0 balance
"""

import psycopg2, os
from decimal import Decimal

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("="*70)
print("2012 WCB BALANCE CHECK")
print("="*70)

# Get all 2012 invoices (positive amounts)
cur.execute("""
    SELECT receipt_id, receipt_date, source_reference, gross_amount, description
    FROM receipts
    WHERE vendor_name = 'WCB' AND fiscal_year = 2012 AND gross_amount > 0
    ORDER BY receipt_date
""")
invoices = cur.fetchall()

print(f"\nINVOICES ({len(invoices)}):")
invoice_total = Decimal('0')
for row in invoices:
    receipt_id, date, ref, amount, desc = row
    invoice_total += Decimal(str(amount))
    desc_short = (desc[:40] if desc else "")
    print(f"  {receipt_id} | {date} | {ref or 'N/A':12} | ${amount:>10,.2f} | {desc_short}")

print(f"\n  Total Invoices: ${invoice_total:,.2f}")

# Get all 2012 payments (negative amounts)
cur.execute("""
    SELECT receipt_id, receipt_date, source_reference, gross_amount, description
    FROM receipts
    WHERE vendor_name = 'WCB' AND fiscal_year = 2012 AND gross_amount < 0
    ORDER BY receipt_date
""")
payments = cur.fetchall()

print(f"\nPAYMENTS ({len(payments)}):")
payment_total = Decimal('0')
for row in payments:
    receipt_id, date, ref, amount, desc = row
    payment_total += Decimal(str(amount))
    desc_short = (desc[:40] if desc else "")
    print(f"  {receipt_id} | {date} | {ref or 'N/A':12} | ${amount:>10,.2f} | {desc_short}")

print(f"\n  Total Payments: ${payment_total:,.2f}")

# Calculate balance
balance = invoice_total + payment_total
print("\n" + "="*70)
print(f"BALANCE: ${invoice_total:,.2f} + ${payment_total:,.2f} = ${balance:,.2f}")
print("="*70)

if abs(balance) < Decimal('0.01'):
    print("\n✅ ACCOUNT BALANCED! Balance = $0.00")
else:
    print(f"\n⚠️  ACCOUNT NOT BALANCED! Balance = ${balance:,.2f}")

conn.close()
