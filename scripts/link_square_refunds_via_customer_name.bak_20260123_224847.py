#!/usr/bin/env python3
"""
Link Square refunds to charters via customer name matching
"""
import psycopg2
import argparse

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    parser = argparse.ArgumentParser(description='Link Square refunds via customer name')
    parser.add_argument('--write', action='store_true', help='Apply changes')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*100)
    print("LINKING SQUARE REFUNDS VIA CUSTOMER NAME")
    print("="*100)
    
    # Get unlinked Square refunds with customer info
    cur.execute("""
        SELECT 
            r.id as refund_id,
            r.refund_date,
            r.amount,
            r.customer,
            r.description
        FROM charter_refunds r
        WHERE r.charter_id IS NULL
        AND r.source_file LIKE 'items-%'
        AND r.customer IS NOT NULL
        AND r.customer != ''
        ORDER BY r.amount DESC
    """)
    
    refunds = cur.fetchall()
    print(f"\nFound {len(refunds)} unlinked Square refunds with customer names\n")
    
    linked_count = 0
    
    for refund_id, refund_date, amount, customer, description in refunds:
        print(f"\n{'='*100}")
        print(f"Refund #{refund_id}: ${amount:,.2f} on {refund_date}")
        print(f"Customer: {customer}")
        print(f"Description: {description}")
        
        # Try to find matching charter via customer name
        # Look within ±60 days of refund date
        cur.execute("""
            SELECT 
                c.charter_id,
                c.reserve_number,
                c.charter_date,
                c.rate,
                cl.client_name,
                c.notes,
                ABS(EXTRACT(EPOCH FROM (c.charter_date - %s::date)) / 86400) as days_diff,
                ABS(c.rate - %s) as amount_diff
            FROM charters c
            LEFT JOIN clients cl ON c.client_id = cl.client_id
            WHERE (
                LOWER(cl.client_name) LIKE LOWER(%s)
                OR LOWER(%s) LIKE LOWER('%' || cl.client_name || '%')
                OR LOWER(cl.client_name) LIKE LOWER('%' || %s || '%')
            )
            AND c.charter_date BETWEEN %s::date - INTERVAL '60 days' 
                                   AND %s::date + INTERVAL '60 days'
            ORDER BY 
                ABS(c.rate - %s) ASC,
                ABS(EXTRACT(EPOCH FROM (c.charter_date - %s::date)) / 86400) ASC
            LIMIT 10
        """, (refund_date, amount, f'%{customer}%', customer, customer, 
              refund_date, refund_date, amount, refund_date))
        
        candidates = cur.fetchall()
        
        if len(candidates) == 0:
            print(f"  [FAIL] No matching charters found")
            continue
        
        print(f"  Found {len(candidates)} potential matches:")
        
        for i, (charter_id, reserve, charter_date, rate, client_name, notes, days_diff, amt_diff) in enumerate(candidates, 1):
            match_score = 100 - (days_diff * 2) - (amt_diff / 10)
            print(f"\n  {i}. Charter {reserve}:")
            print(f"     Date: {charter_date} (±{int(days_diff)} days)")
            print(f"     Amount: ${rate:,.2f} (diff: ${amt_diff:,.2f})")
            print(f"     Client: {client_name}")
            if notes:
                print(f"     Notes: {notes[:80]}")
            print(f"     Match Score: {match_score:.1f}")
        
        # Auto-link if single strong match
        if len(candidates) == 1:
            charter_id, reserve, charter_date, rate, client_name, notes, days_diff, amt_diff = candidates[0]
            
            if days_diff <= 30 and amt_diff <= 100:
                print(f"\n  [OK] STRONG SINGLE MATCH - Auto-linking to {reserve}")
                
                if not args.write:
                    print(f"     [DRY RUN] Would link refund #{refund_id} -> charter {reserve}")
                else:
                    cur.execute("""
                        UPDATE charter_refunds
                        SET charter_id = %s, reserve_number = %s
                        WHERE id = %s
                    """, (charter_id, reserve, refund_id))
                    print(f"     [OK] Linked!")
                
                linked_count += 1
            else:
                print(f"  [WARN]  Single match but weak confidence (±{int(days_diff)} days, ${amt_diff:,.2f} diff)")
                print(f"     MANUAL REVIEW RECOMMENDED")
        
        elif len(candidates) >= 2:
            # Check if first match is significantly better than second
            best = candidates[0]
            second = candidates[1]
            
            best_score = 100 - (best[6] * 2) - (best[7] / 10)
            second_score = 100 - (second[6] * 2) - (second[7] / 10)
            
            if best_score > second_score + 20:  # First is significantly better
                charter_id, reserve, charter_date, rate, client_name, notes, days_diff, amt_diff = best
                print(f"\n  [OK] BEST MATCH (significantly better) - {reserve}")
                
                if not args.write:
                    print(f"     [DRY RUN] Would link refund #{refund_id} -> charter {reserve}")
                else:
                    cur.execute("""
                        UPDATE charter_refunds
                        SET charter_id = %s, reserve_number = %s
                        WHERE id = %s
                    """, (charter_id, reserve, refund_id))
                    print(f"     [OK] Linked!")
                
                linked_count += 1
            else:
                print(f"\n  [WARN]  Multiple similar matches - MANUAL REVIEW NEEDED")
    
    if args.write and linked_count > 0:
        conn.commit()
        print(f"\n[OK] COMMITTED: Linked {linked_count} refunds to charters")
    
    # Final status
    cur.execute("""
        SELECT COUNT(*) 
        FROM charter_refunds 
        WHERE charter_id IS NULL 
        AND source_file LIKE 'items-%'
    """)
    remaining = cur.fetchone()[0]
    
    print("\n" + "="*100)
    print("FINAL RESULTS")
    print("="*100)
    print(f"Square refunds still unlinked: {remaining}")
    print(f"Successfully linked: {linked_count}")
    
    if not args.write:
        print(f"\n[DRY RUN] Would link {linked_count} Square refunds")
        print("Run with --write to apply changes")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
