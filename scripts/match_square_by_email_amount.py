#!/usr/bin/env python3
"""
Match Square payments to charters using customer email, amount, and date.
Matches by:
1. Customer email → client email (exact match)
2. Amount match (±$5 tolerance for tips/fees)
3. Date proximity (±14 days)
4. Client name fuzzy match
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import re

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "***REMOVED***")

def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def normalize_name(name):
    """Normalize name for fuzzy matching."""
    if not name:
        return ""
    return re.sub(r'[^\w\s]', '', name.upper().strip())

def main():
    write_mode = '--write' in sys.argv
    
    print("\n" + "="*100)
    print("MATCH SQUARE PAYMENTS TO CHARTERS BY EMAIL/AMOUNT/DATE")
    print("="*100)
    print(f"\nMode: {'WRITE' if write_mode else 'DRY RUN'}")
    
    if not write_mode:
        print("\n   DRY RUN - Use --write to apply matches\n")
    
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get unmatched Square payments with customer data
    cur.execute("""
        SELECT payment_id, amount, payment_date,
               square_customer_name, square_customer_email,
               square_payment_id, square_card_brand, square_last4
        FROM payments
        WHERE square_payment_id IS NOT NULL
        AND (reserve_number IS NULL OR charter_id IS NULL)
        AND square_customer_email IS NOT NULL
        ORDER BY payment_date DESC
    """)
    
    unmatched = cur.fetchall()
    
    if not unmatched:
        print("  No unmatched Square payments with customer email")
        cur.close()
        conn.close()
        return
    
    print(f"\nFound {len(unmatched)} unmatched Square payments with customer email\n")
    
    # Get all charters with client data
    cur.execute("""
        SELECT c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due,
               cl.client_name, cl.email, cl.phone_number
        FROM charters c
        LEFT JOIN clients cl ON cl.client_id = c.client_id
        WHERE c.charter_date >= '2024-01-01'
        ORDER BY c.charter_date DESC
    """)
    
    charters = cur.fetchall()
    
    print(f"Checking against {len(charters)} recent charters\n")
    
    matched = 0
    skipped = 0
    
    for payment in unmatched:
        payment_id = payment['payment_id']
        amount = float(payment['amount'])
        date = payment['payment_date']
        email = (payment['square_customer_email'] or '').strip().lower()
        name = payment['square_customer_name']
        
        if not email:
            skipped += 1
            continue
        
        # Find matching charters
        best_match = None
        best_score = 0
        
        for charter in charters:
            score = 0
            signals = []
            
            # Email match (exact)
            charter_email = (charter['email'] or '').strip().lower()
            if charter_email and email == charter_email:
                score += 10
                signals.append('email_match')
            
            # Amount match (±$5)
            charter_amount = float(charter['total_amount_due'] or 0)
            amount_diff = abs(amount - charter_amount)
            if amount_diff <= 5.0:
                score += 5
                signals.append(f'amount_match(${amount_diff:.2f})')
            elif amount_diff <= 50.0:
                score += 2
                signals.append(f'amount_close(${amount_diff:.2f})')
            
            # Date proximity
            charter_date = charter['charter_date']
            if charter_date and date:
                try:
                    if isinstance(charter_date, str):
                        charter_dt = datetime.strptime(charter_date, '%Y-%m-%d').date()
                    else:
                        charter_dt = charter_date
                    
                    if isinstance(date, str):
                        payment_dt = datetime.strptime(date, '%Y-%m-%d').date()
                    else:
                        payment_dt = date
                    
                    days_diff = abs((payment_dt - charter_dt).days)
                    
                    if days_diff <= 3:
                        score += 5
                        signals.append('date_close')
                    elif days_diff <= 7:
                        score += 3
                        signals.append('date_nearby')
                    elif days_diff <= 14:
                        score += 1
                        signals.append('date_within_2wks')
                except Exception:
                    pass
            
            # Name match (fuzzy)
            if name and charter['client_name']:
                norm_payment_name = normalize_name(name)
                norm_charter_name = normalize_name(charter['client_name'])
                
                if norm_payment_name and norm_charter_name:
                    if norm_payment_name in norm_charter_name or norm_charter_name in norm_payment_name:
                        score += 3
                        signals.append('name_match')
            
            # Track best match
            if score > best_score and score >= 10:  # Require at least email match
                best_score = score
                best_match = {
                    'charter': charter,
                    'score': score,
                    'signals': signals
                }
        
        if best_match:
            charter = best_match['charter']
            reserve_number = charter['reserve_number']
            charter_id = charter['charter_id']
            
            if write_mode:
                # Update payment
                cur.execute("""
                    UPDATE payments
                    SET charter_id = %s,
                        reserve_number = %s,
                        updated_at = NOW()
                    WHERE payment_id = %s
                """, (charter_id, reserve_number, payment_id))
                
                # Recalculate charter balance
                cur.execute("""
                    WITH payment_sum AS (
                        SELECT COALESCE(SUM(amount), 0) as total_paid
                        FROM payments
                        WHERE reserve_number = %s
                    )
                    UPDATE charters
                    SET paid_amount = ps.total_paid,
                        balance = total_amount_due - ps.total_paid,
                        updated_at = NOW()
                    FROM payment_sum ps
                    WHERE charters.reserve_number = %s
                """, (reserve_number, reserve_number))
                
                print(f"  Matched payment {payment_id} (${amount:.2f}, {email}) to charter {reserve_number}")
                print(f"    Score: {best_match['score']}, Signals: {', '.join(best_match['signals'])}")
                matched += 1
            else:
                print(f"  Would match: Payment {payment_id} (${amount:.2f}, {email}) -> Charter {reserve_number}")
                print(f"    Score: {best_match['score']}, Signals: {', '.join(best_match['signals'])}")
                matched += 1
        else:
            print(f"    No match: Payment {payment_id} (${amount:.2f}, {email}, {name})")
            skipped += 1
    
    if write_mode:
        conn.commit()
        print(f"\n  COMMITTED:")
    else:
        print(f"\nDRY RUN summary:")
    
    print(f"  Matched: {matched}")
    print(f"  Skipped: {skipped}")
    print(f"  Total processed: {len(unmatched)}")
    
    if matched > 0 and not write_mode:
        print("\n  Run with --write to apply these matches")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
