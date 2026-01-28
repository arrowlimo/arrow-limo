#!/usr/bin/env python3
"""
Diagnose WCB invoice/payment linking issue.
Looking for:
1. Payment of $3446.02 on 08/30/2012
2. Payment/waived fee of $593.81
3. Payment of $553.17 on 11/27/2012
4. Related invoices
"""
import psycopg2
import os
import json
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

try:
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("SEARCHING FOR WCB PAYMENTS")
    print("="*80)
    
    # Search for $3446.02 payment
    print("\n1. Looking for $3446.02 payment (Aug 30, 2012)...")
    cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, description, check_number
        FROM banking_transactions
        WHERE ABS(debit_amount - 3446.02) < 0.01
        ORDER BY transaction_date DESC
        LIMIT 10
    """)
    rows = cur.fetchall()
    if rows:
        print(f"   Found {len(rows)} matching transaction(s):")
        for tx_id, tx_date, amount, desc, check in rows:
            print(f"     TX ID {tx_id}: {tx_date} | ${amount:.2f} | Check: {check} | {desc[:50]}")
    else:
        print("   ❌ No $3446.02 payment found")
    
    # Search for $593.81 (voided late fee)
    print("\n2. Looking for $593.81 payment (voided WCB late fee)...")
    cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, description, check_number
        FROM banking_transactions
        WHERE ABS(debit_amount - 593.81) < 0.01
        ORDER BY transaction_date DESC
        LIMIT 10
    """)
    rows = cur.fetchall()
    if rows:
        print(f"   Found {len(rows)} matching transaction(s):")
        for tx_id, tx_date, amount, desc, check in rows:
            print(f"     TX ID {tx_id}: {tx_date} | ${amount:.2f} | Check: {check} | {desc[:50]}")
    else:
        print("   ❌ No $593.81 payment found")
    
    # Search for $553.17 payment
    print("\n3. Looking for $553.17 payment (Nov 27, 2012)...")
    cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, description, check_number
        FROM banking_transactions
        WHERE ABS(debit_amount - 553.17) < 0.01
        ORDER BY transaction_date DESC
        LIMIT 10
    """)
    rows = cur.fetchall()
    if rows:
        print(f"   Found {len(rows)} matching transaction(s):")
        for tx_id, tx_date, amount, desc, check in rows:
            print(f"     TX ID {tx_id}: {tx_date} | ${amount:.2f} | Check: {check} | {desc[:50]}")
    else:
        print("   ❌ No $553.17 payment found")
    
    print("\n" + "="*80)
    print("SEARCHING FOR WCB INVOICES/RECEIPTS")
    print("="*80)
    
    # Search for WCB invoices
    print("\n4. Looking for WCB invoices in receipts table...")
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, description, banking_transaction_id, source_reference
        FROM receipts
        WHERE vendor_name ILIKE '%wcb%' OR vendor_name ILIKE '%workers comp%'
        ORDER BY receipt_date DESC
        LIMIT 20
    """)
    rows = cur.fetchall()
    if rows:
        print(f"   Found {len(rows)} WCB receipts:")
        for rec_id, rec_date, vendor, amount, desc, banking_id, src_ref in rows:
            linked = "✅ Linked" if banking_id else "❌ Unlinked"
            print(f"     Receipt {rec_id}: {rec_date} | {vendor} | ${amount:.2f} | {linked} | Ref: {src_ref}")
            if desc:
                print(f"                   Description: {desc[:60]}")
    else:
        print("   ❌ No WCB receipts found")
    
    print("\n" + "="*80)
    print("CHECKING BANKING_RECEIPT_MATCHING_LEDGER")
    print("="*80)
    
    # Check if any of the payments have linked receipts
    print("\n5. Looking for any links from these transactions...")
    cur.execute("""
        SELECT DISTINCT
            bm.id, bm.banking_transaction_id, bm.receipt_id, 
            bt.debit_amount, bt.transaction_date,
            r.vendor_name, r.gross_amount, r.receipt_date
        FROM banking_receipt_matching_ledger bm
        JOIN banking_transactions bt ON bm.banking_transaction_id = bt.transaction_id
        JOIN receipts r ON bm.receipt_id = r.receipt_id
        WHERE bt.debit_amount IN (3446.02, 593.81, 553.17)
        ORDER BY bt.transaction_date DESC
    """)
    rows = cur.fetchall()
    if rows:
        print(f"   Found {len(rows)} linked pairs:")
        for bm_id, tx_id, rec_id, tx_amount, tx_date, vendor, rec_amount, rec_date in rows:
            print(f"     Link {bm_id}: TX {tx_id} (${tx_amount:.2f} on {tx_date}) → Receipt {rec_id} (${rec_amount:.2f} from {vendor})")
    else:
        print("   ❌ No links found for these amounts")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    # Count totals
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE ABS(debit_amount - 3446.02) < 0.01
           OR ABS(debit_amount - 593.81) < 0.01
           OR ABS(debit_amount - 553.17) < 0.01
    """)
    payment_count = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COUNT(*) FROM receipts
        WHERE vendor_name ILIKE '%wcb%' OR vendor_name ILIKE '%workers comp%'
    """)
    invoice_count = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COUNT(*) FROM banking_receipt_matching_ledger bm
        JOIN banking_transactions bt ON bm.banking_transaction_id = bt.transaction_id
        WHERE bt.debit_amount IN (3446.02, 593.81, 553.17)
    """)
    link_count = cur.fetchone()[0]
    
    print(f"\nPayments found: {payment_count}")
    print(f"WCB invoices found: {invoice_count}")
    print(f"Current links: {link_count}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
