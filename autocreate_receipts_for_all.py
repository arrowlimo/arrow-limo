#!/usr/bin/env python3
"""
AUTO-CREATE RECEIPTS FOR REMAINING UNMATCHED BANKING
All remaining transactions are business/personal expenses - create receipt records
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
    print(f"AUTO-CREATE RECEIPTS FOR UNMATCHED BANKING - {mode}")
    print("=" * 100)
    
    # Get all unmatched banking transactions
    print("\n1️⃣ LOADING UNMATCHED BANKING:")
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount, 
               description, vendor_extracted
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        AND reconciled_receipt_id IS NULL
        ORDER BY transaction_date
    """)
    
    all_trans = cur.fetchall()
    total_amount = sum(abs((c if c else 0) + (d if d else 0)) for _, _, c, d, _, _ in all_trans)
    
    print(f"   Found {len(all_trans)} unmatched transactions | ${total_amount:,.2f}")
    
    # Create receipts for each
    if not DRY_RUN:
        print(f"\n2️⃣ CREATING RECEIPTS:")
        print("-" * 100)
        
        created = 0
        linked = 0
        failed = 0
        
        for trans_id, trans_date, credit, debit, desc, vendor in all_trans:
            try:
                amount = abs((credit if credit else 0) + (debit if debit else 0))
                
                # Determine if credit (income) or debit (expense)
                is_expense = debit is not None and debit != 0
                
                # Create receipt
                cur.execute("""
                    INSERT INTO receipts
                    (receipt_date, vendor_name, description, gross_amount, 
                     expense_account, source_system, created_from_banking, 
                     banking_transaction_id, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s, NOW())
                    RETURNING receipt_id
                """, (
                    trans_date,
                    vendor or desc[:50] if desc else 'Unknown',
                    desc,
                    amount,
                    'Business Expense' if is_expense else 'Income',
                    'AUTO_RECONCILIATION',
                    trans_id
                ))
                
                receipt_id = cur.fetchone()[0]
                created += 1
                
                # Link banking transaction
                cur.execute("""
                    UPDATE banking_transactions
                    SET reconciled_receipt_id = %s, updated_at = NOW()
                    WHERE transaction_id = %s
                """, (receipt_id, trans_id))
                
                linked += 1
                
                conn.commit()
                
                if created % 1000 == 0:
                    print(f"   ... {created} receipts created, {linked} linked")
                    
            except Exception as e:
                failed += 1
                if failed <= 5:
                    print(f"   ❌ Trans {trans_id}: {str(e)[:60]}")
                conn.rollback()
        
        print(f"   ✅ Created: {created} receipts | Linked: {linked} | Failed: {failed}")
    
    else:
        print(f"\n2️⃣ DRY RUN - Would create {len(all_trans)} receipts (${total_amount:,.2f})")
    
    # Verify
    print(f"\n3️⃣ VERIFICATION:")
    print("-" * 100)
    
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE reconciled_payment_id IS NULL AND reconciled_receipt_id IS NULL
    """)
    remaining = cur.fetchone()[0]
    
    print(f"   Remaining unmatched: {remaining}")
    
    if not DRY_RUN:
        cur.execute("""
            SELECT COUNT(*), COUNT(reconciled_payment_id), COUNT(reconciled_receipt_id)
            FROM banking_transactions
        """)
        total, to_pays, to_recs = cur.fetchone()
        linked_total = to_pays + to_recs
        pct = linked_total * 100 // total
        print(f"   OVERALL COMPLETION: {linked_total}/{total} ({pct}%)")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100 + "\n")

if __name__ == "__main__":
    main()
