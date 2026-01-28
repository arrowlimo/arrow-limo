#!/usr/bin/env python3
"""
Link remaining WCB invoices to TX 69282 ($3446.02) to complete the reconciliation.
These are the invoices identified: 145296, 145291, 145292, 145294
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

try:
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("LINKING REMAINING WCB INVOICES TO TX 69282 ($3446.02)")
    print("="*80)
    
    # Receipts to link: 145296, 145291, 145292, 145294
    receipt_ids = [145296, 145291, 145292, 145294]
    payment_tx_id = 69282
    
    print(f"\nLinking {len(receipt_ids)} receipts to TX {payment_tx_id}...")
    
    total_amount = 0.0
    for receipt_id in receipt_ids:
        # Get receipt details
        cur.execute("""
            SELECT receipt_date, gross_amount, description, source_reference
            FROM receipts
            WHERE receipt_id = %s
        """, (receipt_id,))
        
        row = cur.fetchone()
        if row:
            rec_date, amount, desc, src_ref = row
            amount_f = float(amount)
            total_amount += amount_f
            
            # Update receipt with banking_transaction_id
            cur.execute("""
                UPDATE receipts
                SET banking_transaction_id = %s
                WHERE receipt_id = %s
            """, (payment_tx_id, receipt_id))
            
            # Create ledger entry
            cur.execute("""
                INSERT INTO banking_receipt_matching_ledger (
                    banking_transaction_id, receipt_id, match_date, match_type, 
                    match_status, match_confidence, notes, created_by
                ) VALUES (
                    %s, %s, NOW(), %s, %s, %s, %s, %s
                )
            """, (
                payment_tx_id,
                receipt_id,
                "allocation",
                "linked",
                "partial",
                f"amount=${amount_f:.2f}; part of $3446.02 WCB payment",
                "SYSTEM_RECOVERY"
            ))
            
            print(f"  ✓ Receipt {receipt_id}: {rec_date} | ${amount_f:>8.2f} | {src_ref}")
        else:
            print(f"  ✗ Receipt {receipt_id}: NOT FOUND")
    
    conn.commit()
    
    print(f"\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    
    # Now verify all links for TX 69282
    cur.execute("""
        SELECT COUNT(*) as link_count,
               SUM(r.gross_amount) as total_invoice_amount
        FROM banking_receipt_matching_ledger bm
        JOIN receipts r ON bm.receipt_id = r.receipt_id
        WHERE bm.banking_transaction_id = %s
    """, (payment_tx_id,))
    
    link_count, verify_amount = cur.fetchone()
    verify_amount_f = float(verify_amount) if verify_amount else 0.0
    
    print(f"\nPayment TX {payment_tx_id}: $3446.02")
    print(f"Total links: {link_count}")
    print(f"Total invoice amount: ${verify_amount_f:.2f}")
    print(f"Variance: ${3446.02 - verify_amount_f:.2f}")
    
    if abs(3446.02 - verify_amount_f) < 0.01:
        print("\n✅ PERFECT MATCH - PAYMENT IS FULLY RECONCILED!")
    else:
        print(f"\n⚠️  Variance remaining: ${3446.02 - verify_amount_f:.2f}")
    
    # List all linked invoices
    print(f"\nAll {link_count} linked invoices:")
    cur.execute("""
        SELECT r.receipt_id, r.receipt_date, r.gross_amount, r.source_reference, r.description
        FROM banking_receipt_matching_ledger bm
        JOIN receipts r ON bm.receipt_id = r.receipt_id
        WHERE bm.banking_transaction_id = %s
        ORDER BY r.receipt_date ASC
    """, (payment_tx_id,))
    
    rows = cur.fetchall()
    for rec_id, rec_date, amount, src_ref, desc in rows:
        amt_f = float(amount)
        desc_str = (desc[:40] if desc else "")
        print(f"  Receipt {rec_id}: {rec_date} | ${amt_f:>8.2f} | {src_ref} | {desc_str}")
    
    cur.close()
    conn.close()
    
    print("\n✅ Complete!\n")
    
except Exception as e:
    if conn:
        conn.rollback()
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
