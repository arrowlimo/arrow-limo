#!/usr/bin/env python
"""
Check Fibrenew Invoice 5386 from 2013-03-03
Verify if it exists, is paid in full, and linked to payment info
"""

import psycopg2
from datetime import datetime

# Database connection
conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 80)
print("FIBRENEW INVOICE 5386 CHECK - 2013-03-03")
print("=" * 80)

# Check for invoice 5386 in receipts table
print("\n1. Searching for Invoice 5386 in receipts table...")
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.description,
        r.gross_amount,
        r.category,
        r.source_reference,
        r.banking_transaction_id,
        r.created_from_banking
    FROM receipts r
    WHERE (r.description ILIKE '%5386%' OR r.source_reference = '5386')
        AND r.vendor_name ILIKE '%fibrenew%'
    ORDER BY r.receipt_date
""")
invoice_receipts = cur.fetchall()

if invoice_receipts:
    print(f"\n✅ Found {len(invoice_receipts)} receipt(s) for Invoice 5386:")
    for r in invoice_receipts:
        print(f"\n  Receipt ID: {r[0]}")
        print(f"  Date: {r[1]}")
        print(f"  Vendor: {r[2]}")
        print(f"  Description: {r[3]}")
        print(f"  Amount: ${r[4]:,.2f}")
        print(f"  Category: {r[5]}")
        print(f"  Source Reference: {r[6]}")
        print(f"  Banking Transaction ID: {r[7]}")
        print(f"  Created from Banking: {r[8]}")
else:
    print("\n❌ No receipts found for Invoice 5386")

# Check for any Fibrenew entries around 2013-03-03
print("\n\n2. Searching for ALL Fibrenew transactions around March 2013...")
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.description,
        r.gross_amount,
        r.category,
        r.source_reference
    FROM receipts r
    WHERE r.vendor_name ILIKE '%fibrenew%'
        AND r.receipt_date BETWEEN '2013-02-01' AND '2013-04-30'
    ORDER BY r.receipt_date
""")
nearby_receipts = cur.fetchall()

if nearby_receipts:
    print(f"\n✅ Found {len(nearby_receipts)} Fibrenew receipt(s) Feb-Apr 2013:")
    for r in nearby_receipts:
        print(f"\n  Receipt ID: {r[0]}")
        print(f"  Date: {r[1]}")
        print(f"  Vendor: {r[2]}")
        print(f"  Description: {r[3]}")
        print(f"  Amount: ${r[4]:,.2f}")
        print(f"  Category: {r[5]}")
        print(f"  Source Reference: {r[6]}")
else:
    print("\n❌ No Fibrenew receipts found Feb-Apr 2013")

# Check banking transactions
print("\n\n3. Searching for Fibrenew payments in banking_transactions...")
cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.description,
        bt.debit_amount,
        bt.credit_amount,
        bt.category
    FROM banking_transactions bt
    WHERE bt.description ILIKE '%fibrenew%'
        AND bt.transaction_date BETWEEN '2013-02-01' AND '2013-04-30'
    ORDER BY bt.transaction_date
""")
banking_txns = cur.fetchall()

if banking_txns:
    print(f"\n✅ Found {len(banking_txns)} banking transaction(s):")
    for bt in banking_txns:
        print(f"\n  Banking TX ID: {bt[0]}")
        print(f"  Date: {bt[1]}")
        print(f"  Description: {bt[2]}")
        if bt[3]:
            print(f"  Debit: ${bt[3]:,.2f}")
        if bt[4]:
            print(f"  Credit: ${bt[4]:,.2f}")
        print(f"  Category: {bt[5]}")
else:
    print("\n❌ No banking transactions found for Fibrenew in this period")

# Check ALL Fibrenew invoices in system
print("\n\n4. ALL Fibrenew invoices in system (by invoice number in description):")
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.description,
        r.gross_amount,
        r.source_reference
    FROM receipts r
    WHERE r.vendor_name ILIKE '%fibrenew%'
        AND r.description ~ '[0-9]{4,}'
    ORDER BY r.receipt_date
""")
all_fibrenew = cur.fetchall()

if all_fibrenew:
    print(f"\n✅ Found {len(all_fibrenew)} Fibrenew invoice receipts:")
    for r in all_fibrenew:
        print(f"  Date: {r[1]} | Amount: ${r[3]:,.2f} | Receipt#: {r[4]} | Desc: {r[2][:80]}")
else:
    print("\n❌ No Fibrenew invoices found")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("SEARCH COMPLETE")
print("=" * 80)
