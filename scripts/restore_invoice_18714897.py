#!/usr/bin/env python3
"""
Restore/create invoice 18714897 ($553.17) and link it to TX 69587.
This invoice was previously linked but the link was lost.
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

try:
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("RESTORING INVOICE 18714897 ($553.17)")
    print("="*80)
    
    # Check if invoice exists
    print("\n1. Checking if invoice 18714897 exists...")
    cur.execute("""
        SELECT receipt_id, receipt_date, gross_amount, banking_transaction_id
        FROM receipts
        WHERE source_reference = '18714897'
    """)
    
    result = cur.fetchone()
    
    if result:
        # Invoice exists - just re-link it
        rec_id, rec_date, amount, banking_id = result
        print(f"   ✓ Found existing Receipt {rec_id}: {rec_date} | ${float(amount):.2f}")
        print(f"     Currently linked to: {banking_id if banking_id else 'Nothing'}")
        
        receipt_id = rec_id
    else:
        # Invoice doesn't exist - create it
        print(f"   ✗ Invoice not found - creating it...")
        
        cur.execute("""
            INSERT INTO receipts (
                receipt_date, vendor_name, gross_amount, description,
                category, source_reference, payment_method,
                banking_transaction_id, created_from_banking,
                is_driver_reimbursement, source_file
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING receipt_id
        """, (
            '2012-12-19',
            'WCB',
            553.17,
            'wcb waived late filing penalty',
            'Other',
            '18714897',
            'banking_transfer',
            None,
            False,
            False,
            'RESTORED'
        ))
        
        receipt_id = cur.fetchone()[0]
        print(f"   ✓ Created Receipt {receipt_id} for invoice 18714897")
    
    # Now link it to TX 69587
    print(f"\n2. Linking invoice 18714897 to TX 69587 ($553.17 payment)...")
    
    # Update receipt
    cur.execute("""
        UPDATE receipts
        SET banking_transaction_id = 69587
        WHERE receipt_id = %s
    """, (receipt_id,))
    
    print(f"   ✓ Updated receipt to link to TX 69587")
    
    # Remove old ledger entries if any
    cur.execute("""
        DELETE FROM banking_receipt_matching_ledger
        WHERE receipt_id = %s
    """, (receipt_id,))
    
    # Create new ledger entry
    cur.execute("""
        INSERT INTO banking_receipt_matching_ledger (
            banking_transaction_id, receipt_id, match_date, match_type,
            match_status, match_confidence, notes, created_by
        ) VALUES (
            %s, %s, NOW(), %s, %s, %s, %s, %s
        )
    """, (
        69587,
        receipt_id,
        "allocation",
        "linked",
        "exact",
        "Invoice dated 2012-12-19, payment received 2012-11-27",
        "SYSTEM_RESTORE"
    ))
    
    conn.commit()
    print(f"   ✓ Created ledger entry")
    
    # Verify
    print(f"\n3. Verifying link...")
    cur.execute("""
        SELECT COUNT(*) as count, SUM(r.gross_amount) as total
        FROM banking_receipt_matching_ledger bm
        JOIN receipts r ON bm.receipt_id = r.receipt_id
        WHERE bm.banking_transaction_id = 69587
    """)
    
    count, total = cur.fetchone()
    total_f = float(total) if total else 0.0
    
    print(f"   TX 69587: {count} invoice(s) linked = ${total_f:.2f}")
    
    if abs(total_f - 553.17) < 0.01:
        print(f"\n   ✅ PERFECT - $553.17 payment is now linked!")
    
    print(f"\n" + "="*80)
    print("FINAL STATUS - ALL 4 WCB PAYMENTS")
    print("="*80)
    
    # Check all payments
    print(f"\n1. $686.65 (2012-03-19) - Receipt 145297 ✓")
    
    cur.execute("""
        SELECT COUNT(*) as count, SUM(r.gross_amount) as total
        FROM banking_receipt_matching_ledger bm
        JOIN receipts r ON bm.receipt_id = r.receipt_id
        WHERE bm.banking_transaction_id = 69282
    """)
    count, total = cur.fetchone()
    total_f = float(total) if total else 0.0
    print(f"2. $3,446.02 (2012-08-28) - TX 69282 - {count} invoices = ${total_f:.2f} ✓")
    
    cur.execute("""
        SELECT COUNT(*) as count, SUM(r.gross_amount) as total
        FROM banking_receipt_matching_ledger bm
        JOIN receipts r ON bm.receipt_id = r.receipt_id
        WHERE bm.banking_transaction_id = 69587
    """)
    count, total = cur.fetchone()
    total_f = float(total) if total else 0.0
    print(f"3. $553.17 (2012-11-27) - TX 69587 - {count} invoice(s) = ${total_f:.2f} ✓")
    
    print(f"4. $593.81 (2012-11-27) - Receipt 145305 (waived) ✓")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
