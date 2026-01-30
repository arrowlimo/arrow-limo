#!/usr/bin/env python3
"""
Sample Square payment notes to understand what data we have.
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "***REDACTED***")

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "="*100)
    print("SAMPLE SQUARE PAYMENT NOTES")
    print("="*100)
    
    # Sample recent unmatched
    cur.execute("""
        SELECT payment_id, amount, payment_date, notes,
               square_payment_id, square_card_brand, square_last4
        FROM payments
        WHERE (square_payment_id IS NOT NULL OR square_transaction_id IS NOT NULL)
        AND (reserve_number IS NULL OR charter_id IS NULL)
        ORDER BY payment_date DESC
        LIMIT 20
    """)
    
    payments = cur.fetchall()
    
    print(f"\nRecent unmatched Square payments (showing notes field):\n")
    
    for p in payments:
        notes = p['notes'] or "(empty)"
        print(f"Payment {p['payment_id']}: ${p['amount']:.2f} on {p['payment_date']}")
        print(f"  Square ID: {p['square_payment_id']}")
        print(f"  Card: {p['square_card_brand']} ending {p['square_last4']}")
        print(f"  Notes: {notes}")
        print()
    
    # Check if any old Square payments have notes with reserve numbers
    print("\nSample of matched Square payments (to see what notes look like):\n")
    
    cur.execute("""
        SELECT payment_id, amount, payment_date, reserve_number, notes
        FROM payments
        WHERE square_payment_id IS NOT NULL
        AND reserve_number IS NOT NULL
        AND notes IS NOT NULL
        ORDER BY payment_date DESC
        LIMIT 10
    """)
    
    matched = cur.fetchall()
    
    for p in matched:
        print(f"Payment {p['payment_id']}: ${p['amount']:.2f} on {p['payment_date']} → {p['reserve_number']}")
        print(f"  Notes: {p['notes'][:100]}")
        print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
