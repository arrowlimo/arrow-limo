#!/usr/bin/env python3
"""
Match Square payments to charters by extracting reserve numbers from notes field.
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import re

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "***REDACTED***")

def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def extract_reserve_number(text):
    """Extract reserve number from text (5-6 digits)."""
    if not text:
        return None
    # Look for 5-6 digit numbers
    match = re.search(r'\b(\d{5,6})\b', text)
    return match.group(1) if match else None

def main():
    write_mode = '--write' in sys.argv
    
    print("\n" + "="*100)
    print("MATCH SQUARE PAYMENTS TO CHARTERS")
    print("="*100)
    print(f"\nMode: {'WRITE' if write_mode else 'DRY RUN'}")
    
    if not write_mode:
        print("\n⚠️  DRY RUN - Use --write to apply matches\n")
    
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get unmatched Square payments
    cur.execute("""
        SELECT payment_id, amount, payment_date, notes,
               square_payment_id, square_transaction_id
        FROM payments
        WHERE (square_payment_id IS NOT NULL OR square_transaction_id IS NOT NULL)
        AND (reserve_number IS NULL OR charter_id IS NULL)
        ORDER BY payment_date DESC
    """)
    
    unmatched = cur.fetchall()
    
    if not unmatched:
        print("✓ All Square payments are matched!")
        cur.close()
        conn.close()
        return
    
    print(f"\nFound {len(unmatched)} unmatched Square payments\n")
    
    matched = 0
    skipped = 0
    
    for payment in unmatched:
        payment_id = payment['payment_id']
        notes = payment['notes']
        amount = payment['amount']
        date = payment['payment_date']
        
        # Try to extract reserve number
        reserve_number = extract_reserve_number(notes)
        
        if not reserve_number:
            print(f"  ⚠️  Payment {payment_id}: ${amount:.2f} on {date} - No reserve number in notes")
            skipped += 1
            continue
        
        # Find charter
        cur.execute('SELECT charter_id FROM charters WHERE reserve_number = %s', (reserve_number,))
        charter = cur.fetchone()
        
        if not charter:
            print(f"  ⚠️  Payment {payment_id}: ${amount:.2f} on {date} - Reserve {reserve_number} not found")
            skipped += 1
            continue
        
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
            
            print(f"  ✓ Matched payment {payment_id} (${amount:.2f}) to charter {reserve_number}")
            matched += 1
        else:
            print(f"  Would match: Payment {payment_id} (${amount:.2f}) → Charter {reserve_number}")
            matched += 1
    
    if write_mode:
        conn.commit()
        print(f"\n✓ COMMITTED:")
    else:
        print(f"\nDRY RUN summary:")
    
    print(f"  Matched: {matched}")
    print(f"  Skipped: {skipped}")
    print(f"  Total processed: {len(unmatched)}")
    
    if matched > 0 and not write_mode:
        print("\n✓ Run with --write to apply these matches")
    
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
