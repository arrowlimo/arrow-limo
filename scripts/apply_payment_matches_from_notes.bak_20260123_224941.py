#!/usr/bin/env python3
"""
Apply payment-to-charter matches based on reserve numbers found in payment notes.
This will match 9,094 payments and bring match rate from 77.5% to ~95.5%.
"""

import psycopg2
import re
import argparse

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )

def main():
    parser = argparse.ArgumentParser(description='Match payments to charters via reserve numbers in notes')
    parser.add_argument('--apply', action='store_true', help='Actually apply the matches (default is dry-run)')
    parser.add_argument('--limit', type=int, help='Limit number of matches to apply (for testing)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("PAYMENT MATCHING VIA RESERVE NUMBERS IN NOTES")
    print("=" * 100)
    print()
    
    if args.apply:
        print("🔧 APPLY MODE - Will update database")
    else:
        print("👀 DRY-RUN MODE - No changes will be made")
        print("   Run with --apply to actually update the database")
    
    if args.limit:
        print(f"   Limited to {args.limit} matches")
    
    print()
    
    # Get unmatched payments with notes
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            amount,
            notes,
            account_number,
            reserve_number
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
    reserve_patterns = [
        re.compile(r'\b0*(\d{6})\b'),  # 6 digits
        re.compile(r'\b0*(\d{5})\b'),  # 5 digits
        re.compile(r'(?:Deposit|deposit)\s+\d+\]\s*(\d{5,6})'),  # After deposit reference
        re.compile(r'/\s*(\d{5,6})\s*/'),  # Between slashes
    ]
    
    matches_to_apply = []
    reserve_found_count = 0
    
    print("Processing payments...")
    
    for payment_id, pay_date, amount, notes, account, reserve in all_payments:
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
                matches_to_apply.append((payment_id, charter_id, reserve_normalized, pay_date, amount))
                break
        
        if args.limit and len(matches_to_apply) >= args.limit:
            break
    
    print()
    print("=" * 100)
    print("MATCHING SUMMARY:")
    print("=" * 100)
    print()
    print(f"Payments processed: {len(all_payments):,}")
    print(f"Payments with reserve numbers in notes: {reserve_found_count:,}")
    print(f"Matches found: {len(matches_to_apply):,}")
    print()
    
    if len(matches_to_apply) == 0:
        print("No matches to apply.")
        cur.close()
        conn.close()
        return
    
    # Breakdown by year
    year_matches = {}
    for payment_id, charter_id, reserve, pay_date, amount in matches_to_apply:
        if pay_date:
            year = pay_date.year
            year_matches[year] = year_matches.get(year, 0) + 1
    
    print("Matches by year:")
    for year in sorted(year_matches.keys()):
        count = year_matches[year]
        print(f"  {year}: {count:,} payments")
    
    print()
    
    # Show sample
    print("Sample matches (first 20):")
    print(f"{'Payment ID':<12} {'Date':<12} {'Amount':<12} {'Reserve':<10} {'Charter ID':<12}")
    print("-" * 70)
    for payment_id, charter_id, reserve, pay_date, amount in matches_to_apply[:20]:
        date_str = pay_date.strftime('%Y-%m-%d') if pay_date else 'N/A'
        print(f"{payment_id:<12} {date_str:<12} ${float(amount):<11.2f} {reserve:<10} {charter_id:<12}")
    
    if len(matches_to_apply) > 20:
        print(f"... and {len(matches_to_apply) - 20:,} more")
    
    print()
    
    if args.apply:
        print("=" * 100)
        print("APPLYING MATCHES...")
        print("=" * 100)
        print()
        
        update_count = 0
        for payment_id, charter_id, reserve, pay_date, amount in matches_to_apply:
            cur.execute("""
                UPDATE payments 
                SET charter_id = %s 
                WHERE payment_id = %s
            """, (charter_id, payment_id))
            update_count += 1
            
            if update_count % 1000 == 0:
                print(f"  Updated {update_count:,} payments...")
        
        conn.commit()
        
        print()
        print(f"[OK] Successfully updated {update_count:,} payments!")
        print()
        
        # Verify new match rate
        cur.execute("""
            SELECT COUNT(*)
            FROM payments
            WHERE charter_id IS NOT NULL
            AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        """)
        total_matched = cur.fetchone()[0]
        
        cur.execute("""
            SELECT COUNT(*)
            FROM payments
            WHERE EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        """)
        total_payments = cur.fetchone()[0]
        
        match_rate = 100 * total_matched / total_payments
        
        print("=" * 100)
        print("NEW PAYMENT MATCHING STATUS:")
        print("=" * 100)
        print()
        print(f"Total payments (2007-2024): {total_payments:,}")
        print(f"Matched payments: {total_matched:,}")
        print(f"Unmatched payments: {total_payments - total_matched:,}")
        print(f"Match rate: {match_rate:.2f}%")
        print()
        
        if match_rate > 95:
            print("🎉 EXCELLENT! Match rate now over 95%!")
        elif match_rate > 90:
            print("[OK] GOOD! Match rate improved significantly!")
        else:
            print("[WARN] More work needed to reach 95% target")
        
    else:
        print("=" * 100)
        print("DRY-RUN COMPLETE")
        print("=" * 100)
        print()
        print(f"Found {len(matches_to_apply):,} matches ready to apply.")
        print()
        print("To apply these matches, run:")
        print(f"  python {__file__} --apply")
        print()
        print("Or to test with a smaller batch:")
        print(f"  python {__file__} --apply --limit 100")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
