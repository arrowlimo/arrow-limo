#!/usr/bin/env python3
"""
Verify all receipts against banking transactions.
Identify and flag:
1. Receipts with no banking transaction match (orphan receipts)
2. Banking transactions with no receipt match (missing receipts)
3. Obvious import errors (fake vendor names)
4. Unverified banking entries
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
    print("BANKING RECONCILIATION ANALYSIS")
    print("="*100)
    
    # 1. Receipts with NO banking transaction match
    print("\n" + "="*100)
    print("RECEIPTS WITH NO BANKING TRANSACTION MATCH (Orphan Receipts)")
    print("="*100)
    
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount, gl_account_code, receipt_date
        FROM receipts
        WHERE banking_transaction_id IS NULL
        ORDER BY gross_amount DESC
        LIMIT 50
    """)
    
    orphan_results = cur.fetchall()
    orphan_count = 0
    orphan_amount = 0
    
    cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts WHERE banking_transaction_id IS NULL")
    total_orphan = cur.fetchone()
    print(f"\nTotal orphan receipts: {total_orphan[0]:,} (${total_orphan[1]:,.2f})")
    print(f"Showing top 50:\n")
    
    for receipt_id, vendor_name, amount, gl_code, receipt_date in orphan_results:
        orphan_count += 1
        if amount:
            orphan_amount += amount
        amount_str = f"${amount:>10,.2f}" if amount else "NULL    "
        print(f"Receipt {receipt_id}: {amount_str} | {vendor_name:<40} | GL:{gl_code} | {receipt_date}")
    
    # 2. Banking transactions with NO receipt match
    print("\n" + "="*100)
    print("BANKING TRANSACTIONS WITH NO RECEIPT MATCH (Missing Receipts)")
    print("="*100)
    
    cur.execute("""
        SELECT bt.transaction_id, bt.description, bt.debit_amount, bt.credit_amount, bt.verified, bt.transaction_date
        FROM banking_transactions bt
        LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
        WHERE r.receipt_id IS NULL
        AND bt.locked = false
        AND bt.verified = true
        ORDER BY ABS(COALESCE(bt.debit_amount, 0) + COALESCE(bt.credit_amount, 0)) DESC
        LIMIT 50
    """)
    
    missing_results = cur.fetchall()
    print(f"\nShowing verified, unlocked banking transactions missing receipts (top 50):\n")
    
    missing_count = 0
    missing_amount = 0
    for txn_id, desc, debit, credit, verified, txn_date in missing_results:
        missing_count += 1
        amount = debit if debit else -credit
        missing_amount += amount
        verified_str = "✓" if verified else "✗"
        print(f"TXN {txn_id}: ${amount:>10,.2f} | {desc:<50} | Verified:{verified_str} | {txn_date}")
    
    # 3. Obvious import errors (fake vendor names)
    print("\n" + "="*100)
    print("SUSPICIOUS/OBVIOUS ERROR VENDORS")
    print("="*100)
    
    suspicious_patterns = [
        ('000000%', 'OCR/Bank Account Number as vendor'),
        ('%EMAIL TRANSFER%', 'Missing recipient name'),
        ('BILL PAYMENT', 'No vendor identified'),
        ('%DRAFT PURCHASE%', 'Generic - needs verification'),
        ('%CORRECTION%', 'Accounting error - needs review'),
        ('%JOURNAL ENTRY%', 'Fake entry - needs deletion'),
        ('%CHEQUE%', 'Cheque error - needs review'),
        ('%UNKNOWN%', 'Unknown vendor - needs review'),
    ]
    
    for pattern, description in suspicious_patterns:
        cur.execute("""
            SELECT vendor_name, COUNT(*) as count, SUM(gross_amount) as total,
                   MAX(CASE WHEN banking_transaction_id IS NULL THEN 1 ELSE 0 END) as has_orphan
            FROM receipts
            WHERE vendor_name ILIKE %s
            GROUP BY vendor_name, banking_transaction_id IS NULL
            ORDER BY SUM(gross_amount) DESC
            LIMIT 15
        """, (pattern,))
        
        results = cur.fetchall()
        if results:
            print(f"\n{description} ({pattern}):")
            for vendor_name, count, total, has_orphan in results:
                orphan_marker = " [ORPHAN - NO BANKING]" if has_orphan else ""
                print(f"  {vendor_name:<50} {count:>4} receipts  ${total:>12,.2f}{orphan_marker}")
    
    # 4. Specific cases mentioned by user
    print("\n" + "="*100)
    print("SPECIFIC CASES MENTIONED BY USER")
    print("="*100)
    
    # BERGLUND LOUISE
    print("\n[BERGLUND LOUISE] - Accountant Payment")
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount, banking_transaction_id, gl_account_code, receipt_date
        FROM receipts
        WHERE vendor_name ILIKE '%BERGLUND%'
        ORDER BY receipt_date DESC
        LIMIT 10
    """)
    berglund_results = cur.fetchall()
    for receipt_id, vendor_name, amount, bt_id, gl_code, date in berglund_results:
        bt_status = f"Banking TXN: {bt_id}" if bt_id else "NO BANKING MATCH"
        print(f"  Receipt {receipt_id}: ${amount:,.2f} | {vendor_name} | GL:{gl_code} | {bt_status} | {date}")
    
    # 000000171208777 (Bank Account Number)
    print("\n[000000171208777] - Appears to be Bank Account/POS, Not Vendor")
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount, banking_transaction_id, gl_account_code, receipt_date
        FROM receipts
        WHERE vendor_name LIKE '%000000171208777%' OR vendor_name LIKE '%171208777%'
        ORDER BY receipt_date DESC
        LIMIT 10
    """)
    bank_acct_results = cur.fetchall()
    if bank_acct_results:
        for receipt_id, vendor_name, amount, bt_id, gl_code, date in bank_acct_results:
            bt_status = f"Banking TXN: {bt_id}" if bt_id else "NO BANKING MATCH"
            print(f"  Receipt {receipt_id}: ${amount:,.2f} | {vendor_name} | GL:{gl_code} | {bt_status} | {date}")
    else:
        print("  No receipts found with this vendor")
    
    # EMAIL TRANSFER without recipient
    print("\n[EMAIL TRANSFER] - Without recipient name (should have name after 'EMAIL TRANSFER -')")
    cur.execute("""
        SELECT vendor_name, COUNT(*) as count, SUM(gross_amount) as total
        FROM receipts
        WHERE vendor_name = 'EMAIL TRANSFER'
        GROUP BY vendor_name
    """)
    et_results = cur.fetchall()
    for vendor_name, count, total in et_results:
        print(f"  {vendor_name:<50} {count:>4} receipts  ${total:>12,.2f}  [MISSING RECIPIENT]")
    
    # 5. Summary by verification status
    print("\n" + "="*100)
    print("VERIFICATION STATUS SUMMARY")
    print("="*100)
    
    cur.execute("""
        SELECT 
            CASE 
                WHEN banking_transaction_id IS NULL THEN 'Orphan (No Banking)'
                ELSE 'Linked to Banking'
            END as status,
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_amount
        FROM receipts
        GROUP BY CASE WHEN banking_transaction_id IS NULL THEN 'Orphan (No Banking)' ELSE 'Linked to Banking' END
    """)
    
    status_results = cur.fetchall()
    for status, count, total in status_results:
        percentage = (count / 33980) * 100
        print(f"\n{status}")
        print(f"  Receipts: {count:,} ({percentage:.1f}%)")
        print(f"  Amount: ${total:,.2f}")

finally:
    cur.close()
    conn.close()
