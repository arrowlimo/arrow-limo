#!/usr/bin/env python3
"""
LINK CHARGEBACKS/REVERSALS + LARGE CUSTOMER PAYMENTS (Phase 3)
- Chargebacks and reversals
- Large payments ≥$10K (likely customer charters)
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

DRY_RUN = "--dry-run" in __import__("sys").argv

def main():
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    mode = "DRY RUN" if DRY_RUN else "PRODUCTION"
    print("\n" + "=" * 100)
    print(f"CHARGEBACKS/REVERSALS + LARGE PAYMENTS LINKING - {mode}")
    print("=" * 100)
    
    # Get chargebacks
    print("\n1️⃣ LOADING CHARGEBACKS/REVERSALS:")
    print("-" * 100)
    
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount, description
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        AND (
            description ILIKE '%CHARGEBACK%' OR
            description ILIKE '%REVERSAL%' OR
            description ILIKE '%REFUND%' OR
            description ILIKE '%CLAIM%'
        )
        ORDER BY ABS(COALESCE(credit_amount, 0) + COALESCE(debit_amount, 0)) DESC
    """)
    
    chargebacks = cur.fetchall()
    chargeback_amount = sum(abs((c if c else 0) + (d if d else 0)) for _, _, c, d, _ in chargebacks)
    print(f"   Found {len(chargebacks)} chargebacks/reversals | ${chargeback_amount:,.2f}")
    
    # Get large payments
    print("\n2️⃣ LOADING LARGE PAYMENTS (≥$10K):")
    print("-" * 100)
    
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount, description
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        AND ABS(COALESCE(credit_amount, 0) + COALESCE(debit_amount, 0)) >= 10000
        ORDER BY ABS(COALESCE(credit_amount, 0) + COALESCE(debit_amount, 0)) DESC
    """)
    
    large_payments = cur.fetchall()
    large_amount = sum(abs((c if c else 0) + (d if d else 0)) for _, _, c, d, _ in large_payments)
    print(f"   Found {len(large_payments)} large payments | ${large_amount:,.2f}")
    
    # Combine
    all_trans = chargebacks + large_payments
    total_amount = chargeback_amount + large_amount
    
    print(f"\n3️⃣ COMBINED SUMMARY:")
    print("-" * 100)
    print(f"   Chargebacks/Reversals: {len(chargebacks):4d} | ${chargeback_amount:12,.2f}")
    print(f"   Large Payments:        {len(large_payments):4d} | ${large_amount:12,.2f}")
    print(f"   TOTAL:                 {len(all_trans):4d} | ${total_amount:12,.2f}")
    
    # Sample large payments
    if large_payments:
        print(f"\n4️⃣ SAMPLE LARGE PAYMENTS:")
        print("-" * 100)
        for trans_id, date, credit, debit, desc in large_payments[:5]:
            amount = abs((credit if credit else 0) + (debit if debit else 0))
            print(f"   {trans_id:8d} | {date} | ${amount:10,.2f} | {desc[:60]}")
    
    # Link them
    if not DRY_RUN:
        print(f"\n5️⃣ LINKING TRANSACTIONS:")
        print("-" * 100)
        
        linked = 0
        failed = 0
        
        for trans_id, date, credit, debit, desc in all_trans:
            try:
                amount = abs((credit if credit else 0) + (debit if debit else 0))
                
                # Determine reserve_number type
                desc_upper = desc.upper() if desc else ""
                if any(x in desc_upper for x in ['CHARGEBACK', 'REVERSAL', 'REFUND', 'CLAIM']):
                    reserve = 'CHARGEBACK_' + str(trans_id)
                else:
                    reserve = 'LARGE_PAY_' + str(trans_id)
                
                # Create payment
                cur.execute("""
                    INSERT INTO payments
                    (reserve_number, amount, payment_date, payment_method, status, notes, created_at, updated_at)
                    VALUES (%s, %s, %s, 'bank_transfer', 'paid', %s, NOW(), NOW())
                    RETURNING payment_id
                """, (reserve, amount, date, f'Large/Chargeback: {desc[:80]}'))
                
                payment_id = cur.fetchone()[0]
                
                # Link banking
                cur.execute("""
                    UPDATE banking_transactions
                    SET reconciled_payment_id = %s, updated_at = NOW()
                    WHERE transaction_id = %s
                """, (payment_id, trans_id))
                
                conn.commit()
                linked += 1
                
            except Exception as e:
                failed += 1
                if failed <= 3:
                    print(f"   ❌ Trans {trans_id}: {str(e)[:60]}")
        
        print(f"   ✅ Linked: {linked} | Failed: {failed}")
    
    else:
        print(f"\n5️⃣ DRY RUN - Would link {len(all_trans)} transactions (${total_amount:,.2f})")
    
    # Verify
    print(f"\n6️⃣ VERIFICATION:")
    print("-" * 100)
    
    cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE reconciled_payment_id IS NULL")
    remaining = cur.fetchone()[0]
    
    print(f"   Remaining unmatched: {remaining}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100 + "\n")

if __name__ == "__main__":
    main()
