#!/usr/bin/env python3
"""
Identify and list all suspicious/error receipts that should be deleted.
Create a clean report without modifying database yet.
"""

import psycopg2
import os
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

try:
    print("\n" + "="*100)
    print("IDENTIFIED SUSPICIOUS RECEIPTS FOR DELETION")
    print("="*100)
    
    # 1. JOURNAL ENTRY - Fake entries
    print("\n1. JOURNAL ENTRY (Fake/Duplicate Entries) - DELETE")
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount, banking_transaction_id, receipt_date
        FROM receipts
        WHERE vendor_name ILIKE 'JOURNAL ENTRY%'
        ORDER BY gross_amount DESC
    """)
    je_results = cur.fetchall()
    je_count = len(je_results)
    je_amount = sum(r[2] for r in je_results if r[2])
    print(f"   Count: {je_count} receipts | Amount: ${je_amount:,.2f}")
    for receipt_id, vendor_name, amount, bt_id, date in je_results:
        bt_status = f"(BT:{bt_id})" if bt_id else "(NO BANKING)"
        print(f"     Receipt {receipt_id}: ${amount:,.2f} | {vendor_name} | {bt_status} | {date}")
    
    # 2. Bank account numbers as vendors
    print("\n2. BANK ACCOUNT NUMBERS AS VENDOR (OCR Error) - DELETE/REVIEW")
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount, banking_transaction_id, receipt_date
        FROM receipts
        WHERE vendor_name LIKE '000000%'
        ORDER BY gross_amount DESC
    """)
    ba_results = cur.fetchall()
    ba_count = len(ba_results)
    ba_amount = sum(r[2] for r in ba_results if r[2])
    print(f"   Count: {ba_count} receipts | Amount: ${ba_amount:,.2f}")
    for receipt_id, vendor_name, amount, bt_id, date in ba_results:
        bt_status = f"(BT:{bt_id})" if bt_id else "(NO BANKING)"
        print(f"     Receipt {receipt_id}: ${amount:,.2f} | {vendor_name} | {bt_status} | {date}")
    
    # 3. HEFFNER with NULL amount - Duplicates/errors
    print("\n3. HEFFNER WITH NULL AMOUNT (Duplicate/Import Error) - DELETE")
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount, banking_transaction_id, receipt_date
        FROM receipts
        WHERE vendor_name ILIKE 'HEFFNER%'
        AND gross_amount IS NULL
        ORDER BY receipt_date DESC
    """)
    hf_null_results = cur.fetchall()
    hf_null_count = len(hf_null_results)
    print(f"   Count: {hf_null_count} receipts")
    for receipt_id, vendor_name, amount, bt_id, date in hf_null_results[:20]:
        bt_status = f"(BT:{bt_id})" if bt_id else "(NO BANKING)"
        print(f"     Receipt {receipt_id}: {vendor_name} | {bt_status} | {date}")
    
    # 4. OPENING BALANCE entries
    print("\n4. OPENING BALANCE (Use Manual Entries Instead) - DELETE")
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount, banking_transaction_id, receipt_date
        FROM receipts
        WHERE vendor_name ILIKE 'OPENING BALANCE%'
        ORDER BY gross_amount DESC
    """)
    ob_results = cur.fetchall()
    ob_count = len(ob_results)
    ob_amount = sum(r[2] for r in ob_results if r[2])
    print(f"   Count: {ob_count} receipts | Amount: ${ob_amount:,.2f}")
    for receipt_id, vendor_name, amount, bt_id, date in ob_results:
        bt_status = f"(BT:{bt_id})" if bt_id else "(NO BANKING)"
        amount_str = f"${amount:,.2f}" if amount else "NULL"
        print(f"     Receipt {receipt_id}: {amount_str} | {vendor_name} | {bt_status} | {date}")
    
    # 5. Orphan receipts (No banking transaction)
    print("\n5. ORPHAN RECEIPTS (No Banking Transaction Match) - REVIEW/DELETE")
    cur.execute("""
        SELECT vendor_name, COUNT(*) as count, SUM(gross_amount) as total
        FROM receipts
        WHERE banking_transaction_id IS NULL
        GROUP BY vendor_name
        ORDER BY SUM(gross_amount) DESC
        LIMIT 30
    """)
    orphan_results = cur.fetchall()
    orphan_total_count = 0
    orphan_total_amount = 0
    cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts WHERE banking_transaction_id IS NULL")
    orphan_totals = cur.fetchone()
    print(f"   TOTAL ORPHAN: {orphan_totals[0]:,} receipts | Amount: ${orphan_totals[1] if orphan_totals[1] else 0:,.2f}")
    print(f"   Top 30 vendors:")
    for vendor_name, count, total in orphan_results:
        total_str = f"${total:,.2f}" if total else "NULL"
        print(f"     {vendor_name:<50} {count:>4} receipts  {total_str:>12}")
    
    # 6. DUPLICATE TELUS entries
    print("\n6. DUPLICATE/IGNORE ENTRIES (Marked in Vendor Name) - DELETE")
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount, banking_transaction_id, receipt_date
        FROM receipts
        WHERE vendor_name ILIKE '%DUPLICATE%IGNORE%'
        OR vendor_name ILIKE '%IGNORE%'
        ORDER BY gross_amount DESC
    """)
    dup_results = cur.fetchall()
    dup_count = len(dup_results)
    dup_amount = sum(r[2] for r in dup_results if r[2])
    print(f"   Count: {dup_count} receipts | Amount: ${dup_amount:,.2f}")
    for receipt_id, vendor_name, amount, bt_id, date in dup_results:
        bt_status = f"(BT:{bt_id})" if bt_id else "(NO BANKING)"
        print(f"     Receipt {receipt_id}: ${amount:,.2f} | {vendor_name} | {bt_status} | {date}")
    
    print("\n" + "="*100)
    print("SUMMARY")
    print("="*100)
    print(f"\nClear Deletion Candidates:")
    print(f"  JOURNAL ENTRY: {je_count} receipts ({je_amount:,.2f})")
    print(f"  HEFFNER NULL: {hf_null_count} receipts")
    print(f"  OPENING BALANCE: {ob_count} receipts ({ob_amount:,.2f})")
    print(f"  DUPLICATE/IGNORE: {dup_count} receipts ({dup_amount:,.2f})")
    print(f"  SUBTOTAL: {je_count + hf_null_count + ob_count + dup_count} receipts ({je_amount + ob_amount + dup_amount:,.2f})")
    
    print(f"\nReview/Conditional Delete:")
    print(f"  BANK ACCOUNT VENDORS (OCR): {ba_count} receipts ({ba_amount:,.2f})")
    print(f"  ORPHAN (No Banking): {orphan_totals[0]:,} receipts ({orphan_totals[1] if orphan_totals[1] else 0:,.2f})")
    
    print("\n" + "="*100)
    
except Exception as e:
    print(f"Error: {e}")
    raise

finally:
    cur.close()
    conn.close()
