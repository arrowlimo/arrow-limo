#!/usr/bin/env python3
"""
Check payment notes for reserve numbers and matching clues.
"""

import psycopg2
import re

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("CHECKING PAYMENT NOTES FOR MATCHING CLUES")
    print("=" * 100)
    print()
    
    # Get unmatched payments with notes
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            account_number,
            reserve_number,
            amount,
            notes
        FROM payments
        WHERE reserve_number IS NULL
        AND EXTRACT(YEAR FROM payment_date) = 2012
        AND notes IS NOT NULL
        AND notes != ''
        ORDER BY payment_date
        LIMIT 100
    """)
    
    payments_with_notes = cur.fetchall()
    
    print(f"Found {len(payments_with_notes)} unmatched 2012 payments with notes")
    print()
    
    # Pattern to find reserve numbers (6 digits)
    reserve_pattern = re.compile(r'\b0*(\d{5,6})\b')
    
    matches_found = []
    
    print(f"{'Payment ID':<12} {'Date':<12} {'Amount':<12} {'Notes (excerpt)':<60}")
    print("-" * 100)
    
    for payment_id, pay_date, account, reserve, amount, notes in payments_with_notes[:30]:
        date_str = pay_date.strftime('%Y-%m-%d') if pay_date else 'N/A'
        notes_short = (notes[:57] + '...') if len(notes) > 60 else notes
        
        # Look for reserve numbers in notes
        reserve_matches = reserve_pattern.findall(notes)
        if reserve_matches:
            notes_short += f" [RESERVES: {', '.join(reserve_matches[:3])}]"
        
        print(f"{payment_id:<12} {date_str:<12} ${float(amount):<11.2f} {notes_short:<60}")
        
        # Try to match if reserve number found in notes
        for found_reserve in reserve_matches:
            cur.execute("""
                SELECT charter_id, reserve_number
                FROM charters
                WHERE reserve_number = %s
                LIMIT 1
            """, (found_reserve.zfill(6),))
            
            charter = cur.fetchone()
            if charter:
                charter_id, charter_reserve = charter
                matches_found.append((payment_id, charter_id, found_reserve))
                print(f"  → CAN MATCH to Charter {charter_id} (Reserve {charter_reserve})")
    
    print()
    print("=" * 100)
    print("SUMMARY:")
    print("=" * 100)
    print()
    print(f"Payments checked: {len(payments_with_notes)}")
    print(f"Matches found via notes: {len(matches_found)}")
    print()
    
    if matches_found:
        print("[OK] Found payments that can be matched via reserve numbers in notes!")
        print()
        print("Sample SQL updates:")
        for payment_id, charter_id, reserve in matches_found[:10]:
            print(f"  -- Reserve {reserve}: UPDATE payments SET charter_id = {charter_id} WHERE payment_id = {payment_id};")
    
    # Check all 2012 unmatched with notes
    cur.execute("""
        SELECT COUNT(*)
        FROM payments
        WHERE reserve_number IS NULL
        AND EXTRACT(YEAR FROM payment_date) = 2012
        AND notes IS NOT NULL
        AND notes != ''
    """)
    
    total_with_notes = cur.fetchone()[0]
    
    print()
    print(f"Total 2012 unmatched with notes: {total_with_notes:,}")
    if len(payments_with_notes) > 0:
        print(f"Estimated matchable (based on sample): ~{int(total_with_notes * len(matches_found) / len(payments_with_notes))} payments")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
