"""
Apply matches for LMS Sync Import payments that have reserve numbers but no charter_id.

This handles payments where reserve_number is populated but charter_id is NULL/0.
"""

import psycopg2
import os
import argparse

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    parser = argparse.ArgumentParser(description='Apply charter matches for payments with reserve numbers')
    parser.add_argument('--apply', action='store_true', help='Actually update database (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("MATCHING PAYMENTS TO CHARTERS BY RESERVE NUMBER")
    print("=" * 100)
    print()
    
    if not args.apply:
        print("🔍 DRY-RUN MODE - No changes will be made")
        print("   Use --apply flag to actually update database")
        print()
    
    # Get all unmatched payments that have reserve numbers
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.reserve_number,
            p.amount,
            p.notes
        FROM payments p
        WHERE (p.charter_id IS NULL OR p.charter_id = 0)
        AND p.reserve_number IS NOT NULL
        AND p.reserve_number != ''
        ORDER BY p.payment_date DESC
    """)
    
    unmatched_with_reserve = cur.fetchall()
    print(f"Total unmatched payments with reserve numbers: {len(unmatched_with_reserve)}")
    print()
    
    matches = []
    not_found = []
    
    for payment_id, pdate, reserve, amount, notes in unmatched_with_reserve:
        # Find charter with matching reserve number
        cur.execute("""
            SELECT charter_id, charter_date, status
            FROM charters
            WHERE reserve_number = %s
        """, (reserve,))
        
        charter_row = cur.fetchone()
        
        if charter_row:
            charter_id, cdate, status = charter_row
            matches.append({
                'payment_id': payment_id,
                'payment_date': pdate,
                'reserve_number': reserve,
                'amount': amount,
                'charter_id': charter_id,
                'charter_date': cdate,
                'charter_status': status
            })
        else:
            not_found.append({
                'payment_id': payment_id,
                'reserve_number': reserve,
                'amount': amount
            })
    
    print(f"Matches found: {len(matches)}")
    print(f"Charters NOT found: {len(not_found)}")
    print()
    
    if matches:
        print("=" * 100)
        print(f"SAMPLE MATCHES (showing first 20 of {len(matches)}):")
        print("=" * 100)
        print()
        
        for i, match in enumerate(matches[:20], 1):
            print(f"{i}. Payment {match['payment_id']} (Reserve {match['reserve_number']}): ${match['amount']:,.2f}")
            print(f"   → Charter {match['charter_id']} | Status: {match['charter_status'] or 'None'}")
            print()
        
        if len(matches) > 20:
            print(f"... and {len(matches) - 20} more matches")
            print()
        
        if args.apply:
            print("=" * 100)
            print("APPLYING MATCHES...")
            print("=" * 100)
            print()
            
            update_count = 0
            for i, match in enumerate(matches, 1):
                cur.execute("""
                    UPDATE payments
                    SET charter_id = %s
                    WHERE payment_id = %s
                """, (match['charter_id'], match['payment_id']))
                
                update_count += 1
                if update_count % 100 == 0:
                    print(f"Updated {update_count} payments...")
            
            conn.commit()
            print(f"\n[OK] Successfully updated {update_count} payments")
            
            # Verify new match rate
            cur.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE charter_id IS NOT NULL AND charter_id != 0) as matched,
                    COUNT(*) as total
                FROM payments
                WHERE EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
            """)
            matched, total = cur.fetchone()
            match_rate = (matched / total * 100) if total > 0 else 0
            
            print()
            print("=" * 100)
            print("NEW MATCH STATISTICS:")
            print("=" * 100)
            print(f"Total payments (2007-2024): {total:,}")
            print(f"Matched: {matched:,} ({match_rate:.2f}%)")
            print(f"Unmatched: {total - matched:,} ({100 - match_rate:.2f}%)")
            print("=" * 100)
        else:
            print("=" * 100)
            print("DRY-RUN SUMMARY:")
            print("=" * 100)
            print(f"Would update {len(matches)} payments")
            print()
            print("Run with --apply to actually update the database")
            print("=" * 100)
    
    if not_found:
        print()
        print("=" * 100)
        print(f"CHARTERS NOT FOUND ({len(not_found)} payments):")
        print("=" * 100)
        print()
        
        for i, nf in enumerate(not_found[:10], 1):
            print(f"{i}. Payment {nf['payment_id']} | Reserve {nf['reserve_number']} | ${nf['amount']:,.2f}")
        
        if len(not_found) > 10:
            print(f"... and {len(not_found) - 10} more")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
