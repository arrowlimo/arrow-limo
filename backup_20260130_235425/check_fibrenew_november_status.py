#!/usr/bin/env python3
"""Check Fibrenew November 2025 invoice and payment status."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("="*100)
print("NOVEMBER 2025 FIBRENEW INVOICE")
print("="*100)

# Get November Fibrenew invoice
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
           gst_amount, net_amount, description
    FROM receipts
    WHERE vendor_name ILIKE '%fibrenew%'
    AND receipt_date >= '2025-11-01'
    ORDER BY receipt_date DESC
""")

invoice = cur.fetchone()
if invoice:
    print(f"\nInvoice Receipt ID: {invoice[0]}")
    print(f"Date: {invoice[1]}")
    print(f"Vendor: {invoice[2]}")
    print(f"Gross Amount: ${invoice[3]:.2f}")
    print(f"GST: ${invoice[4]:.2f}")
    print(f"Net Amount: ${invoice[5]:.2f}")
    print(f"Description: {invoice[6]}")
    invoice_amount = invoice[3]
else:
    print("\nNo November 2025 Fibrenew invoice found")
    invoice_amount = 0

# Get November rent payments
print("\n" + "="*100)
print("NOVEMBER 2025 RENT PAYMENTS (Fibrenew-related)")
print("="*100)

cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
    FROM receipts
    WHERE (vendor_name ILIKE '%office rent%' 
           OR description ILIKE '%fibrenew%'
           OR (vendor_name ILIKE '%point of sale%' AND category = 'rent'))
    AND receipt_date >= '2025-11-01'
    ORDER BY receipt_date
""")

payments = cur.fetchall()
total_paid = 0
print(f"\n{'Date':<12} | {'Amount':>10} | Vendor / Description")
print("-"*100)
for p in payments:
    print(f"{p[1]!s:<12} | ${p[3]:>9.2f} | {p[2]} - {p[4][:40]}")
    total_paid += p[3]

print("-"*100)
print(f"{'TOTAL PAID':>23s}: ${total_paid:.2f}")

if invoice_amount > 0:
    balance = invoice_amount - total_paid
    print(f"{'Invoice Amount':<23s}: ${invoice_amount:.2f}")
    print(f"{'Balance Remaining':<23s}: ${balance:.2f}")
    
    if abs(balance) < 0.01:
        print("\n✅ PAID IN FULL")
    elif balance > 0:
        print(f"\n⚠️  UNPAID: ${balance:.2f} still owed")
    else:
        print(f"\n✅ OVERPAID: ${-balance:.2f} credit")

conn.close()
