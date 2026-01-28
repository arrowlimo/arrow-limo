#!/usr/bin/env python3
"""
Extract reserve numbers from payment notes/descriptions and match to charters.
"""

import psycopg2
import re

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("MATCHING PAYMENTS VIA RESERVE NUMBERS IN NOTES/DESCRIPTIONS")
    print("=" * 100)
    print()
    
    # Get unmatched payments with notes (all years, not just 2012)
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            amount,
            notes
        FROM payments
        WHERE charter_id IS NULL
        AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        AND notes IS NOT NULL
        AND notes != ''
        ORDER BY payment_date
    """)
    
    all_payments = cur.fetchall()
    
    print(f"Total unmatched payments with notes: {len(all_payments):,}")
    print()
    
    # Patterns to find reserve numbers
    # LMS format: "005689", "002732", etc (5-6 digits)
    # Also try deposit format: "[LMS Deposit 0000257] 014817"
    reserve_patterns = [
        re.compile(r'\b0*(\d{6})\b'),  # 6 digits (most common)
        re.compile(r'\b0*(\d{5})\b'),  # 5 digits
        re.compile(r'(?:Deposit|deposit)\s+\d+\]\s*(\d{5,6})'),  # After deposit reference
        re.compile(r'/\s*(\d{5,6})\s*/'),  # Between slashes
    ]
    
    matches_found = []
    reserve_found_count = 0
    
    print("Sample payments with reserve numbers in notes:")
    print(f"{'Payment ID':<12} {'Date':<12} {'Amount':<12} {'Found Reserve':<15} {'Match Status':<40}")
    print("-" * 100)
    
    sample_shown = 0
    for payment_id, pay_date, amount, notes in all_payments:
        if not notes:
            continue
        
        found_reserves = []
        for pattern in reserve_patterns:
            matches = pattern.findall(notes)
            if matches:
                found_reserves.extend(matches)
        
        if not found_reserves:
            continue
        
        reserve_found_count += 1
        
        # Try to match each found reserve
        matched = False
        for reserve_num in found_reserves:
            # Normalize reserve number (pad to 6 digits)
            reserve_normalized = reserve_num.zfill(6)
            
            # Check if charter exists
            cur.execute("""
                SELECT charter_id, reserve_number, account_number
                FROM charters
                WHERE reserve_number = %s
                LIMIT 1
            """, (reserve_normalized,))
            
            charter = cur.fetchone()
            if charter:
                charter_id, charter_reserve, charter_account = charter
                matches_found.append((payment_id, charter_id, reserve_normalized, notes[:50]))
                matched = True
                
                if sample_shown < 50:
                    date_str = pay_date.strftime('%Y-%m-%d') if pay_date else 'N/A'
                    print(f"{payment_id:<12} {date_str:<12} ${float(amount):<11.2f} {reserve_normalized:<15} [OK] Charter {charter_id}")
                    sample_shown += 1
                break
        
        if not matched and sample_shown < 50:
            date_str = pay_date.strftime('%Y-%m-%d') if pay_date else 'N/A'
            reserve_display = found_reserves[0] if found_reserves else 'None'
            print(f"{payment_id:<12} {date_str:<12} ${float(amount):<11.2f} {reserve_display:<15} [FAIL] No charter found")
            sample_shown += 1
    
    print()
    print(f"... (showing first {sample_shown} payments with reserve numbers)")
    print()
    
    print("=" * 100)
    print("MATCHING SUMMARY:")
    print("=" * 100)
    print()
    print(f"Total unmatched payments with notes: {len(all_payments):,}")
    print(f"Payments with reserve numbers in notes: {reserve_found_count:,}")
    print(f"Successfully matched to charters: {len(matches_found):,}")
    print()
    
    if len(matches_found) > 0:
        match_rate = 100 * len(matches_found) / reserve_found_count
        print(f"[OK] Match rate: {match_rate:.1f}% of payments with reserve numbers")
        print()
        
        # Breakdown by year
        print("Matches by year:")
        year_matches = {}
        for payment_id, charter_id, reserve, notes in matches_found:
            cur.execute("SELECT EXTRACT(YEAR FROM payment_date) FROM payments WHERE payment_id = %s", (payment_id,))
            year = cur.fetchone()
            if year:
                year = int(year[0])
                year_matches[year] = year_matches.get(year, 0) + 1
        
        for year in sorted(year_matches.keys()):
            count = year_matches[year]
            print(f"  {year}: {count:,} payments")
        
        print()
        print("Would you like to apply these matches? This would update the database.")
        print()
        print("Sample SQL (first 10 matches):")
        for payment_id, charter_id, reserve, notes in matches_found[:10]:
            print(f"  UPDATE payments SET charter_id = {charter_id} WHERE payment_id = {payment_id}; -- Reserve {reserve}")
    else:
        print("[WARN] No matches found. Reserve numbers in notes may not match charter records.")
    
    # Show sample notes to help understand format
    print()
    print("=" * 100)
    print("SAMPLE NOTE FORMATS:")
    print("=" * 100)
    print()
    cur.execute("""
        SELECT DISTINCT LEFT(notes, 80) as sample_note
        FROM payments
        WHERE charter_id IS NULL
        AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        AND notes IS NOT NULL
        AND notes != ''
        ORDER BY sample_note
        LIMIT 20
    """)
    
    for row in cur.fetchall():
        print(f"  {row[0]}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
