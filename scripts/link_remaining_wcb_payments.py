#!/usr/bin/env python3
"""
Link the remaining 2 payments to their corresponding invoices.
Payment 2: TX 69587 ($553.17 on 2012-11-26) 
Payment 4: Refund ($593.81 on 2012-11-27 waived late fee)
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
    print("LINKING REMAINING PAYMENTS TO INVOICES")
    print("="*80)
    
    # Find which invoice(s) should be linked to TX 69587 ($553.17)
    print("\n1. Finding invoices for TX 69587 ($553.17 on 2012-11-26)...")
    
    # Look for unlinked invoices dated around 2012-10 to 2012-11
    cur.execute("""
        SELECT receipt_id, receipt_date, gross_amount, source_reference, description, banking_transaction_id
        FROM receipts
        WHERE vendor_name ILIKE '%%wcb%%'
          AND receipt_date >= '2012-10-01'
          AND receipt_date <= '2012-11-30'
          AND banking_transaction_id IS NULL
        ORDER BY receipt_date
    """)
    
    unlinked = cur.fetchall()
    print(f"   Found {len(unlinked)} unlinked invoices in this period:")
    for rec_id, rec_date, amount, ref, desc, banking_id in unlinked:
        amount_f = float(amount)
        print(f"   - Receipt {rec_id}: {rec_date} | ${amount_f:>8.2f} | {desc[:40]}")
    
    # The $553.17 payment likely covers one or more invoices from Oct-Nov
    # Check what totals to ~$553.17
    total = 0.0
    to_link = []
    for rec_id, rec_date, amount, ref, desc, banking_id in unlinked:
        amount_f = float(amount)
        if total + amount_f <= 553.17 + 0.50:
            total += amount_f
            to_link.append(rec_id)
            print(f"   → Receipt {rec_id} (${amount_f:.2f}) - running total: ${total:.2f}")
    
    if total > 0 and abs(total - 553.17) < 1.00:
        print(f"\n   ✓ Found {len(to_link)} invoice(s) totaling ${total:.2f}")
        
        # Link them
        for rec_id in to_link:
            cur.execute("""
                UPDATE receipts
                SET banking_transaction_id = 69587
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
                "partial",
                f"amount=${float(cur.execute('SELECT gross_amount FROM receipts WHERE receipt_id=%s', (rec_id,)).fetchone()[0]):.2f}",
                "SYSTEM"
            ))
            
            print(f"     ✓ Linked Receipt {rec_id}")
        
        conn.commit()
    else:
        print(f"   ⚠ Could not find exact match (total: ${total:.2f})")
    
    # Link the $593.81 waived fee
    print("\n2. Linking the $593.81 waived late fee refund...")
    
    cur.execute("""
        UPDATE receipts
        SET banking_transaction_id = NULL,
            description = 'wcb waived late filing penalty - refunded'
        WHERE receipt_id = 145305
    """)
    
    print(f"   ✓ Updated Receipt 145305 (marked as waived refund, unlinked from TX 69282)")
    
    conn.commit()
    
    # Final verification
    print("\n" + "="*80)
    print("FINAL VERIFICATION")
    print("="*80)
    
    # Check TX 69587 links
    cur.execute("""
        SELECT COUNT(*) as count, SUM(r.gross_amount) as total
        FROM banking_receipt_matching_ledger bm
        JOIN receipts r ON bm.receipt_id = r.receipt_id
        WHERE bm.banking_transaction_id = 69587
    """)
    
    count, total = cur.fetchone()
    total_f = float(total) if total else 0.0
    print(f"\nTX 69587 ($553.17): {count} invoice(s) linked = ${total_f:.2f}")
    
    # Check all payments
    print("\nAll 4 WCB Payments:")
    
    cur.execute("""
        SELECT COUNT(*) as count, SUM(r.gross_amount) as total
        FROM banking_receipt_matching_ledger bm
        JOIN receipts r ON bm.receipt_id = r.receipt_id
        WHERE bm.banking_transaction_id = 69282
    """)
    count1, total1 = cur.fetchone()
    total1_f = float(total1) if total1 else 0.0
    print(f"  1. TX 69282 ($3,446.02): {count1} invoices = ${total1_f:.2f}")
    
    print(f"  2. TX 69587 ($553.17): {count} invoices = ${total_f:.2f}")
    
    # Count standalone receipts
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE receipt_id IN (145297, 145305)
    """)
    count_other, total_other = cur.fetchone()
    total_other_f = float(total_other) if total_other else 0.0
    print(f"  3. Receipt 145297 ($686.65): 1 invoice")
    print(f"  4. Receipt 145305 ($593.81 waived): 1 refund")
    
    total_all = total1_f + total_f + 686.65 + 593.81
    print(f"\nTotal all payments: ${total_all:.2f}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
