#!/usr/bin/env python3
"""
LINK CUSTOMER PAYMENTS BY AMOUNT/DATE MATCHING (Phase 4)
- Match banking transactions to charters by amount (±$0.01) and date (±3 days)
- Focus on medium ($1K-$10K) and small (<$1K) payments
"""

import os
import psycopg2
from decimal import Decimal

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
    print(f"CUSTOMER PAYMENTS BY AMOUNT/DATE MATCHING - {mode}")
    print("=" * 100)
    
    # Get unmatched banking (exclude very small deposits which are often fees)
    print("\n1️⃣ LOADING UNMATCHED BANKING TRANSACTIONS:")
    print("-" * 100)
    
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount, description
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        AND ABS(COALESCE(credit_amount, 0) + COALESCE(debit_amount, 0)) > 10  -- Ignore tiny amounts
        ORDER BY transaction_date DESC
    """)
    
    all_trans = cur.fetchall()
    print(f"   Found {len(all_trans)} unmatched banking transactions")
    
    # Get all charters with amounts
    print("\n2️⃣ LOADING CHARTERS FOR MATCHING:")
    print("-" * 100)
    
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date, total_amount_due, paid_amount
        FROM charters
        WHERE charter_date IS NOT NULL
        AND total_amount_due IS NOT NULL
    """)
    
    all_charters = cur.fetchall()
    print(f"   Found {len(all_charters)} charters")
    
    # Try to match each banking transaction to charters
    print("\n3️⃣ MATCHING BY AMOUNT/DATE:")
    print("-" * 100)
    
    matched = []
    no_match = []
    multi_match = []
    
    for trans_id, trans_date, credit, debit, desc in all_trans:
        trans_amount = abs((credit if credit else 0) + (debit if debit else 0))
        
        # Find matching charters (amount ±$1, date ±7 days, prefer closer matches)
        candidates = []
        for charter_id, reserve_num, charter_date, total_due, paid_amt in all_charters:
            # Amount match (±$1)
            if abs(float(total_due) - float(trans_amount)) <= 1.00:
                # Date match (±7 days)
                if charter_date and abs((charter_date - trans_date).days) <= 7:
                    candidates.append((charter_id, reserve_num, total_due))
        
        if len(candidates) == 1:
            matched.append((trans_id, candidates[0][1], trans_amount, desc))
        elif len(candidates) > 1:
            multi_match.append((trans_id, len(candidates), trans_amount, desc))
        else:
            no_match.append((trans_id, trans_amount, desc))
    
    print(f"   Exact matches (1:1): {len(matched)}")
    print(f"   Multiple matches:    {len(multi_match)}")
    print(f"   No matches:          {len(no_match)}")
    print(f"   Total analyzed:      {len(all_trans)}")
    
    matched_amount = sum(m[2] for m in matched)
    print(f"\n   📊 MATCHED TOTAL: {len(matched)} trans | ${matched_amount:,.2f}")
    
    # Link matched transactions
    if not DRY_RUN:
        print(f"\n4️⃣ LINKING MATCHED TRANSACTIONS:")
        print("-" * 100)
        
        linked = 0
        failed = 0
        
        for trans_id, reserve_number, amount, desc in matched:
            try:
                # Check if payment already exists for this reserve
                cur.execute("""
                    SELECT payment_id FROM payments
                    WHERE reserve_number = %s
                    LIMIT 1
                """, (reserve_number,))
                
                result = cur.fetchone()
                if result:
                    payment_id = result[0]
                else:
                    # Create new payment record
                    cur.execute("""
                        INSERT INTO payments
                        (reserve_number, amount, payment_date, payment_method, status, notes, created_at, updated_at)
                        VALUES (%s, %s, CURRENT_DATE, 'bank_transfer', 'paid', %s, NOW(), NOW())
                        RETURNING payment_id
                    """, (reserve_number, amount, f'Customer payment: {desc[:80]}'))
                    
                    payment_id = cur.fetchone()[0]
                
                # Link banking transaction
                cur.execute("""
                    UPDATE banking_transactions
                    SET reconciled_payment_id = %s, updated_at = NOW()
                    WHERE transaction_id = %s
                """, (payment_id, trans_id))
                
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
        print(f"\n4️⃣ DRY RUN - Would link {len(matched)} transactions (${matched_amount:,.2f})")
    
    # Verify
    print(f"\n5️⃣ VERIFICATION:")
    print("-" * 100)
    
    cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE reconciled_payment_id IS NULL")
    remaining = cur.fetchone()[0]
    
    print(f"   Remaining unmatched: {remaining}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100 + "\n")

if __name__ == "__main__":
    main()
