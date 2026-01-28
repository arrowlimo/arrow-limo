#!/usr/bin/env python3
"""
Link $553.17 payment (TX 69587, received 2012-11-27) to the Dec 19, 2012 invoice.
The invoice date is 2012-12-19 but payment was received 2012-11-27.
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
    print("LINKING $553.17 PAYMENT TO DEC 19 INVOICE")
    print("="*80)
    
    # Find invoice(s) for 12/19/2012
    print("\n1. Finding December 19, 2012 invoice(s)...")
    cur.execute("""
        SELECT receipt_id, receipt_date, gross_amount, source_reference, description, banking_transaction_id
        FROM receipts
        WHERE vendor_name ILIKE '%%wcb%%'
          AND receipt_date = '2012-12-19'
        ORDER BY gross_amount DESC
    """)
    
    results = cur.fetchall()
    print(f"   Found {len(results)} invoice(s):")
    
    total_amount = 0.0
    receipt_ids = []
    
    for rec_id, rec_date, amount, ref, desc, banking_id in results:
        amount_f = float(amount)
        total_amount += amount_f
        receipt_ids.append(rec_id)
        linked_status = "✓ Already linked to TX " + str(banking_id) if banking_id else "✗ Not linked"
        print(f"   - Receipt {rec_id}: {rec_date} | ${amount_f:>8.2f} | {ref} | {linked_status}")
    
    # If no Dec 19 invoices found, search for unlinked invoices that might match
    if not results:
        print("\n   No Dec 19 invoices found. Searching for unlinked invoices matching $553.17...")
        cur.execute("""
            SELECT receipt_id, receipt_date, gross_amount, source_reference, description
            FROM receipts
            WHERE vendor_name ILIKE '%%wcb%%'
              AND ABS(gross_amount - 553.17) < 0.01
              AND banking_transaction_id IS NULL
              AND receipt_date >= '2012-11-01'
              AND receipt_date <= '2012-12-31'
        """)
        
        result = cur.fetchone()
        if result:
            rec_id, rec_date, amount, ref, desc = result
            amount_f = float(amount)
            receipt_ids = [rec_id]
            total_amount = amount_f
            print(f"   Found: Receipt {rec_id}: {rec_date} | ${amount_f:.2f} | {ref}")
    
    if receipt_ids:
        print(f"\n2. Linking {len(receipt_ids)} invoice(s) totaling ${total_amount:.2f} to TX 69587...")
        
        for rec_id in receipt_ids:
            # Update receipt with banking_transaction_id
            cur.execute("""
                UPDATE receipts
                SET banking_transaction_id = 69587
                WHERE receipt_id = %s
            """, (rec_id,))
            
            print(f"   ✓ Updated Receipt {rec_id}")
            
            # Create/update ledger entry
            cur.execute("""
                DELETE FROM banking_receipt_matching_ledger
                WHERE receipt_id = %s
            """, (rec_id,))
            
            cur.execute("""
                INSERT INTO banking_receipt_matching_ledger (
                    banking_transaction_id, receipt_id, match_date, match_type,
                    match_status, match_confidence, notes, created_by
                ) VALUES (
                    %s, %s, NOW(), %s, %s, %s, %s, %s
                )
            """, (
                69587,
                rec_id,
                "allocation",
                "linked",
                "exact" if abs(total_amount - 553.17) < 0.01 else "partial",
                f"Received 2012-11-27, invoice dated 2012-12-19",
                "SYSTEM"
            ))
            
            print(f"   ✓ Created ledger entry for Receipt {rec_id}")
        
        conn.commit()
        
        # Verify
        print(f"\n3. Verifying link...")
        cur.execute("""
            SELECT COUNT(*) as count, SUM(r.gross_amount) as total
            FROM banking_receipt_matching_ledger bm
            JOIN receipts r ON bm.receipt_id = r.receipt_id
            WHERE bm.banking_transaction_id = 69587
        """)
        
        count, verify_total = cur.fetchone()
        verify_total_f = float(verify_total) if verify_total else 0.0
        
        print(f"   TX 69587: {count} invoice(s) linked = ${verify_total_f:.2f}")
        
        if abs(verify_total_f - 553.17) < 0.01:
            print(f"\n   ✅ PERFECT MATCH - $553.17 payment is fully linked!")
        else:
            print(f"\n   ⚠️  Variance: ${553.17 - verify_total_f:.2f}")
    else:
        print(f"\n   ✗ No invoices found to link")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
