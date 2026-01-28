#!/usr/bin/env python3
"""
Quick WCB status check - focus on the 4 payments.
"""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("="*70)
print("WCB PAYMENT DETAILS - ALL 4 PAYMENTS")
print("="*70)

# The 4 WCB payments
payments = [
    (145297, "Receipt", "2012-03-19"),
    (69282, "Banking TX", "2012-08-28"),
    (69587, "Banking TX", "2012-11-27"),
    (145305, "Receipt", "2012-11-27"),
]

for payment_id, payment_type, payment_date in payments:
    if payment_type == "Receipt":
        cur.execute("""
            SELECT gross_amount, description, vendor_name
            FROM receipts
            WHERE receipt_id = %s
        """, (payment_id,))
        row = cur.fetchone()
        if row:
            amount, desc, vendor = row
            print(f"\n✓ Receipt {payment_id}")
            print(f"  Date: {payment_date}")
            print(f"  Amount: ${amount:,.2f}")
            print(f"  Vendor: {vendor}")
            print(f"  Desc: {desc}")
            
            # Check linked invoices
            cur.execute("""
                SELECT COUNT(*), COALESCE(SUM(r.gross_amount), 0)
                FROM banking_receipt_matching_ledger brml
                JOIN receipts r ON r.receipt_id = brml.receipt_id
                WHERE brml.banking_transaction_id IS NULL 
                  AND brml.receipt_id = %s
            """, (payment_id,))
            count, total = cur.fetchone()
            # Actually that's wrong query, let me try this:
            
            cur.execute("""
                SELECT COUNT(*), COALESCE(SUM(r.gross_amount), 0)
                FROM banking_receipt_matching_ledger brml
                JOIN receipts r ON r.receipt_id = brml.receipt_id
                WHERE brml.banking_transaction_id = %s
            """, (payment_id,))
            count, total = cur.fetchone()
            print(f"  Linked Invoices: {count} = ${total:,.2f}")
        else:
            print(f"\n✗ Receipt {payment_id} NOT FOUND")
    else:
        cur.execute("""
            SELECT credit_amount, description
            FROM banking_transactions
            WHERE transaction_id = %s
        """, (payment_id,))
        row = cur.fetchone()
        if row:
            amount, desc = row
            print(f"\n✓ Banking TX {payment_id}")
            print(f"  Date: {payment_date}")
            print(f"  Amount: ${amount:,.2f}")
            print(f"  Desc: {desc}")
            
            # Check linked invoices
            cur.execute("""
                SELECT COUNT(*), COALESCE(SUM(r.gross_amount), 0)
                FROM banking_receipt_matching_ledger brml
                JOIN receipts r ON r.receipt_id = brml.receipt_id
                WHERE brml.banking_transaction_id = %s
            """, (payment_id,))
            count, total = cur.fetchone()
            print(f"  Linked Invoices: {count} = ${total:,.2f}")
        else:
            print(f"\n✗ Banking TX {payment_id} NOT FOUND")

print(f"\n{'='*70}")
print("INVOICE COUNT BY VENDOR")
print("="*70)

cur.execute("""
    SELECT vendor_name, COUNT(*), COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE vendor_name LIKE 'WCB%' OR vendor_name IS NULL
    GROUP BY vendor_name
    ORDER BY vendor_name
""")

for vendor, count, total in cur.fetchall():
    vendor_display = vendor if vendor else "(NULL)"
    print(f"{vendor_display:40} | {count:3} invoices | ${total:10,.2f}")

conn.close()
