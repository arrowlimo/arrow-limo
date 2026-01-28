#!/usr/bin/env python3
"""
Examine banking descriptions for ambiguous receipt types.
Shows detailed banking context for DRAFT, BILL PAYMENT, BUSINESS EXPENSE, LFG.
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

try:
    # DRAFT PURCHASE - what do banking descriptions say?
    print("\n" + "="*100)
    print("DRAFT PURCHASE (8 receipts, $18,686)")
    print("="*100)
    cur.execute("""
        SELECT r.receipt_id, r.vendor_name, r.gross_amount, bt.description
        FROM receipts r
        LEFT JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
        WHERE r.vendor_name ILIKE 'DRAFT PURCHASE%'
        AND r.gl_account_code = '6900'
        ORDER BY r.gross_amount DESC
    """)
    for receipt_id, vendor_name, amount, banking_desc in cur.fetchall():
        print(f"\nReceipt {receipt_id}: ${amount:.2f}")
        print(f"  Vendor: {vendor_name}")
        print(f"  Banking: {banking_desc}")

    # BILL PAYMENT
    print("\n" + "="*100)
    print("BILL PAYMENT (6 receipts, $15,025)")
    print("="*100)
    cur.execute("""
        SELECT r.receipt_id, r.vendor_name, r.gross_amount, bt.description
        FROM receipts r
        LEFT JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
        WHERE r.vendor_name ILIKE 'BILL PAYMENT%'
        AND r.gl_account_code = '6900'
        ORDER BY r.gross_amount DESC
    """)
    for receipt_id, vendor_name, amount, banking_desc in cur.fetchall():
        print(f"\nReceipt {receipt_id}: ${amount:.2f}")
        print(f"  Vendor: {vendor_name}")
        print(f"  Banking: {banking_desc}")

    # BUSINESS EXPENSE
    print("\n" + "="*100)
    print("BUSINESS EXPENSE (7 receipts, $9,688)")
    print("="*100)
    cur.execute("""
        SELECT r.receipt_id, r.vendor_name, r.gross_amount, bt.description
        FROM receipts r
        LEFT JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
        WHERE r.vendor_name ILIKE 'BUSINESS EXPENSE%'
        AND r.gl_account_code = '6900'
        ORDER BY r.gross_amount DESC
    """)
    for receipt_id, vendor_name, amount, banking_desc in cur.fetchall():
        print(f"\nReceipt {receipt_id}: ${amount:.2f}")
        print(f"  Vendor: {vendor_name}")
        print(f"  Banking: {banking_desc}")

    # LFG BUSINESS PAD
    print("\n" + "="*100)
    print("LFG BUSINESS PAD (57 receipts, $8,799)")
    print("="*100)
    cur.execute("""
        SELECT r.receipt_id, r.vendor_name, r.gross_amount, bt.description, COUNT(*) OVER() as total
        FROM receipts r
        LEFT JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
        WHERE r.vendor_name ILIKE 'LFG BUSINESS PAD%'
        AND r.gl_account_code = '6900'
        ORDER BY r.gross_amount DESC
        LIMIT 10
    """)
    results = cur.fetchall()
    if results:
        print(f"  Total: {results[0][4]} receipts (showing first 10)")
        for receipt_id, vendor_name, amount, banking_desc, _ in results:
            print(f"\n  Receipt {receipt_id}: ${amount:.2f}")
            print(f"    Banking: {banking_desc}")

    # DEBIT VIA DRAFT
    print("\n" + "="*100)
    print("DEBIT VIA DRAFT (3 receipts, $9,021)")
    print("="*100)
    cur.execute("""
        SELECT r.receipt_id, r.vendor_name, r.gross_amount, bt.description
        FROM receipts r
        LEFT JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
        WHERE r.vendor_name ILIKE 'DEBIT VIA DRAFT%'
        AND r.gl_account_code = '6900'
        ORDER BY r.gross_amount DESC
    """)
    for receipt_id, vendor_name, amount, banking_desc in cur.fetchall():
        print(f"\nReceipt {receipt_id}: ${amount:.2f}")
        print(f"  Vendor: {vendor_name}")
        print(f"  Banking: {banking_desc}")

    # BANK DRAFT
    print("\n" + "="*100)
    print("BANK DRAFT (3 receipts, $6,407)")
    print("="*100)
    cur.execute("""
        SELECT r.receipt_id, r.vendor_name, r.gross_amount, bt.description
        FROM receipts r
        LEFT JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
        WHERE r.vendor_name ILIKE 'BANK DRAFT%'
        AND r.gl_account_code = '6900'
        ORDER BY r.gross_amount DESC
    """)
    for receipt_id, vendor_name, amount, banking_desc in cur.fetchall():
        print(f"\nReceipt {receipt_id}: ${amount:.2f}")
        print(f"  Vendor: {vendor_name}")
        print(f"  Banking: {banking_desc}")

finally:
    cur.close()
    conn.close()
