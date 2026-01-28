"""
Re-match payments to verified 2012 CIBC banking transactions.
Restores payment-banking links that were removed during verified data import.
"""

import os
import psycopg2
from datetime import timedelta

def get_db_connection():
    """Get PostgreSQL connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def match_payments_to_banking():
    """Match payments to banking transactions using amount and date."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Find unmatched payments from 2012
        print("🔍 Finding unmatched 2012 payments...")
        cur.execute("""
            SELECT payment_id, payment_date, amount, payment_method, notes
            FROM payments
            WHERE banking_transaction_id IS NULL
            AND payment_date >= '2012-01-01'
            AND payment_date <= '2012-12-31'
            ORDER BY payment_date, amount
        """)
        
        unmatched_payments = cur.fetchall()
        print(f"   Found {len(unmatched_payments)} unmatched payments")
        
        if len(unmatched_payments) == 0:
            print("[OK] No unmatched payments found!")
            return
        
        matched_count = 0
        manual_review = []
        
        for payment_id, payment_date, amount, payment_method, notes in unmatched_payments:
            # Try to find matching banking transaction
            # Look for credits (deposits) within +/- 2 days of payment date
            cur.execute("""
                SELECT transaction_id, transaction_date, description, credit_amount
                FROM banking_transactions
                WHERE account_number = '0228362'
                AND transaction_date BETWEEN %s AND %s
                AND credit_amount = %s
                AND transaction_id NOT IN (
                    SELECT banking_transaction_id 
                    FROM payments 
                    WHERE banking_transaction_id IS NOT NULL
                )
                ORDER BY ABS(EXTRACT(EPOCH FROM (transaction_date - %s::timestamp)))
                LIMIT 1
            """, (
                payment_date - timedelta(days=2),
                payment_date + timedelta(days=2),
                amount,
                payment_date
            ))
            
            match = cur.fetchone()
            
            if match:
                transaction_id, trans_date, description, credit_amount = match
                
                # Update payment with banking_transaction_id
                cur.execute("""
                    UPDATE payments
                    SET banking_transaction_id = %s,
                        updated_at = NOW()
                    WHERE payment_id = %s
                """, (transaction_id, payment_id))
                
                matched_count += 1
                print(f"   [OK] Matched payment {payment_id} (${amount:.2f} on {payment_date}) → banking {transaction_id}")
            else:
                manual_review.append({
                    'payment_id': payment_id,
                    'date': payment_date,
                    'amount': amount,
                    'method': payment_method,
                    'notes': notes
                })
        
        conn.commit()
        
        # Summary
        print(f"\n" + "="*60)
        print(f"[OK] MATCHING COMPLETE")
        print(f"="*60)
        print(f"Matched: {matched_count}")
        print(f"Require manual review: {len(manual_review)}")
        print(f"="*60)
        
        if manual_review:
            print(f"\n[WARN]  Payments requiring manual review:")
            for p in manual_review[:10]:  # Show first 10
                print(f"   Payment {p['payment_id']}: ${p['amount']:.2f} on {p['date']} ({p['method']})")
            if len(manual_review) > 10:
                print(f"   ... and {len(manual_review) - 10} more")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[FAIL] ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()

def rebuild_banking_payment_links():
    """Rebuild banking_payment_links table for 2012."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("\n🔗 Rebuilding banking_payment_links for 2012...")
        
        # Find all 2012 payments with banking_transaction_id
        cur.execute("""
            SELECT payment_id, banking_transaction_id
            FROM payments
            WHERE banking_transaction_id IS NOT NULL
            AND banking_transaction_id IN (
                SELECT transaction_id FROM banking_transactions
                WHERE account_number = '0228362'
                AND transaction_date >= '2012-01-01'
                AND transaction_date <= '2012-12-31'
            )
        """)
        
        links = cur.fetchall()
        print(f"   Found {len(links)} payment-banking relationships")
        
        if len(links) == 0:
            return
        
        # Insert into banking_payment_links
        inserted = 0
        for payment_id, banking_transaction_id in links:
            cur.execute("""
                INSERT INTO banking_payment_links (
                    payment_id,
                    banking_transaction_id,
                    created_at
                )
                VALUES (%s, %s, NOW())
                ON CONFLICT (payment_id, banking_transaction_id) DO NOTHING
            """, (payment_id, banking_transaction_id))
            
            if cur.rowcount > 0:
                inserted += 1
        
        conn.commit()
        print(f"   [OK] Inserted {inserted} new links")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[FAIL] ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    print("="*60)
    print("2012 Payment-Banking Link Restoration")
    print("="*60)
    print()
    
    # Step 1: Match payments to banking transactions
    match_payments_to_banking()
    
    # Step 2: Rebuild banking_payment_links table
    rebuild_banking_payment_links()
    
    print("\n[OK] Link restoration complete!")
