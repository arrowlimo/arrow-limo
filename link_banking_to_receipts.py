#!/usr/bin/env python3
"""
LINK BANKING TRANSACTIONS TO RECEIPTS
- Match by vendor_name + amount + date
- This links business expenses already recorded
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

DRY_RUN = "--dry-run" in __import__("sys").argv

def main():
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    mode = "DRY RUN" if DRY_RUN else "PRODUCTION"
    print("\n" + "=" * 100)
    print(f"LINK BANKING TO RECEIPTS - {mode}")
    print("=" * 100)
    
    # Get unmatched banking
    print("\n1️⃣ LOADING UNMATCHED BANKING:")
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount, 
               description, vendor_extracted
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        AND reconciled_receipt_id IS NULL
    """)
    
    all_trans = cur.fetchall()
    print(f"   Found {len(all_trans)} unmatched banking transactions")
    
    # Get all receipts
    print("\n2️⃣ LOADING RECEIPTS:")
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, net_amount, 
               canonical_vendor
        FROM receipts
        WHERE banking_transaction_id IS NULL
    """)
    
    all_receipts = cur.fetchall()
    print(f"   Found {len(all_receipts)} receipts without banking link")
    
    # Try to match each banking to receipts
    print("\n3️⃣ MATCHING BY VENDOR + AMOUNT + DATE:")
    print("-" * 100)
    
    matched = []
    
    for trans_id, trans_date, credit, debit, desc, vendor_ext in all_trans:
        trans_amount = abs((credit if credit else 0) + (debit if debit else 0))
        
        # Find matching receipts
        for receipt_id, receipt_date, vendor_name, gross_amt, net_amt, canonical_vendor in all_receipts:
            # Try matching by amount
            amount_match = False
            if gross_amt and abs(float(gross_amt) - float(trans_amount)) <= 0.01:
                amount_match = True
            elif net_amt and abs(float(net_amt) - float(trans_amount)) <= 0.01:
                amount_match = True
            
            if amount_match:
                # Try matching by vendor name
                vendor_match = False
                desc_upper = (desc or "").upper()
                vendor_upper = (vendor_name or "").upper()
                vendor_ext_upper = (vendor_ext or "").upper()
                canonical_upper = (canonical_vendor or "").upper()
                
                # Check if any vendor identifier is in the banking description
                if vendor_upper in desc_upper or vendor_ext_upper in desc_upper:
                    vendor_match = True
                    
                # Or if banking description is in the vendor name
                if vendor_upper in desc_upper or canonical_upper in desc_upper:
                    vendor_match = True
                
                if vendor_match:
                    # Also check date ±3 days
                    if abs((trans_date - receipt_date).days) <= 3:
                        matched.append((trans_id, receipt_id, trans_amount, vendor_name))
                        break
    
    print(f"   Found {len(matched)} matches")
    
    if matched:
        amount = sum(m[2] for m in matched)
        print(f"   Matched amount: ${amount:,.2f}")
    
    # Link them
    if not DRY_RUN and matched:
        print(f"\n4️⃣ LINKING TRANSACTIONS:")
        print("-" * 100)
        
        linked = 0
        failed = 0
        
        for trans_id, receipt_id, amount, vendor in matched:
            try:
                cur.execute("""
                    UPDATE banking_transactions
                    SET reconciled_receipt_id = %s, updated_at = NOW()
                    WHERE transaction_id = %s
                """, (receipt_id, trans_id))
                
                # Also link the receipt back
                cur.execute("""
                    UPDATE receipts
                    SET banking_transaction_id = %s
                    WHERE receipt_id = %s
                """, (trans_id, receipt_id))
                
                conn.commit()
                linked += 1
                
                if linked % 500 == 0:
                    print(f"   ... {linked} linked")
                    
            except Exception as e:
                failed += 1
                if failed <= 3:
                    print(f"   ❌ Trans {trans_id}: {str(e)[:60]}")
        
        print(f"   ✅ Linked: {linked} | Failed: {failed}")
    
    else:
        if matched:
            print(f"\n4️⃣ DRY RUN - Would link {len(matched)} transactions")
        else:
            print(f"\n4️⃣ No matches found")
    
    # Verify
    print(f"\n5️⃣ VERIFICATION:")
    print("-" * 100)
    
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE reconciled_payment_id IS NULL AND reconciled_receipt_id IS NULL
    """)
    remaining = cur.fetchone()[0]
    
    print(f"   Remaining unmatched: {remaining}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100 + "\n")

if __name__ == "__main__":
    main()
