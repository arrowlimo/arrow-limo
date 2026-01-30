#!/usr/bin/env python3
"""
Link Square refunds via square_payment_id, then find charter via payment date/amount
"""
import psycopg2
import argparse

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def main():
    parser = argparse.ArgumentParser(description='Link Square refunds via transaction IDs')
    parser.add_argument('--write', action='store_true', help='Apply changes')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*100)
    print("LINKING SQUARE REFUNDS VIA TRANSACTION IDs")
    print("="*100)
    
    # Find Square refunds that match payments via square_payment_id
    cur.execute("""
        SELECT 
            r.id as refund_id,
            r.refund_date,
            r.amount as refund_amount,
            r.square_payment_id,
            p.payment_id,
            p.payment_date,
            p.amount as payment_amount,
            p.charter_id,
            p.reserve_number,
            p.account_number
        FROM charter_refunds r
        JOIN payments p ON r.square_payment_id = p.square_payment_id
        WHERE r.charter_id IS NULL
        AND r.source_file LIKE 'items-%'
        AND r.square_payment_id IS NOT NULL
        AND r.square_payment_id != ''
    """)
    
    matches = cur.fetchall()
    print(f"\nFound {len(matches)} Square refunds linked to payments\n")
    
    linked_count = 0
    needs_payment_linkage = []
    
    for refund_id, refund_date, refund_amt, square_id, payment_id, payment_date, payment_amt, charter_id, reserve, account in matches:
        if charter_id and reserve:
            print(f"[OK] Refund #{refund_id}: ${refund_amt:,.2f} -> Charter {reserve}")
            print(f"   Payment #{payment_id} already has charter linkage")
            
            if not args.write:
                print(f"   [DRY RUN] Would link refund to charter {reserve}")
            else:
                cur.execute("""
                    UPDATE charter_refunds
                    SET charter_id = %s, reserve_number = %s
                    WHERE id = %s
                """, (charter_id, reserve, refund_id))
                print(f"   [OK] Linked!")
            
            linked_count += 1
        else:
            print(f"[WARN]  Refund #{refund_id}: ${refund_amt:,.2f} -> Payment #{payment_id}")
            print(f"   Payment exists but has NO charter linkage")
            print(f"   Payment date: {payment_date}, Amount: ${payment_amt:,.2f}, Account: {account}")
            needs_payment_linkage.append((refund_id, refund_amt, payment_id, payment_date, payment_amt, account))
    
    # Try to find charters for payments without charter_id
    if needs_payment_linkage:
        print("\n" + "="*100)
        print("ATTEMPTING TO LINK PAYMENTS TO CHARTERS")
        print("="*100)
        
        for refund_id, refund_amt, payment_id, payment_date, payment_amt, account in needs_payment_linkage:
            # Try to find charter by payment date + amount match
            cur.execute("""
                SELECT charter_id, reserve_number, charter_date, rate, client_id
                FROM charters
                WHERE ABS(EXTRACT(EPOCH FROM (charter_date - %s::date)) / 86400) <= 30
                AND ABS(rate - %s) <= 50
                ORDER BY ABS(EXTRACT(EPOCH FROM (charter_date - %s::date))) ASC,
                         ABS(rate - %s) ASC
                LIMIT 5
            """, (payment_date, payment_amt, payment_date, payment_amt))
            
            candidates = cur.fetchall()
            
            if len(candidates) == 1:
                # Single match - high confidence
                charter_id, reserve, charter_date, rate, client_id = candidates[0]
                print(f"\n[OK] SINGLE MATCH for Payment #{payment_id}:")
                print(f"   Payment: {payment_date}, ${payment_amt:,.2f}")
                print(f"   Charter: {reserve}, {charter_date}, ${rate:,.2f}")
                
                if not args.write:
                    print(f"   [DRY RUN] Would link payment #{payment_id} -> charter {reserve}")
                    print(f"   [DRY RUN] Would link refund #{refund_id} -> charter {reserve}")
                else:
                    # Link payment to charter
                    cur.execute("""
                        UPDATE payments
                        SET charter_id = %s, reserve_number = %s
                        WHERE payment_id = %s
                    """, (charter_id, reserve, payment_id))
                    
                    # Link refund to charter
                    cur.execute("""
                        UPDATE charter_refunds
                        SET charter_id = %s, reserve_number = %s
                        WHERE id = %s
                    """, (charter_id, reserve, refund_id))
                    
                    print(f"   [OK] Linked both payment and refund to charter {reserve}")
                
                linked_count += 1
            elif len(candidates) > 1:
                print(f"\n[WARN]  MULTIPLE MATCHES for Payment #{payment_id}:")
                print(f"   Payment: {payment_date}, ${payment_amt:,.2f}")
                print(f"   Found {len(candidates)} possible charters:")
                for charter_id, reserve, charter_date, rate, client_id in candidates:
                    date_diff = (charter_date - payment_date).days if charter_date else 999
                    print(f"      {reserve}: {charter_date} (±{abs(date_diff)} days), ${rate:,.2f}")
                print(f"   MANUAL REVIEW NEEDED")
            else:
                print(f"\n[FAIL] NO MATCH for Payment #{payment_id}")
                print(f"   Payment: {payment_date}, ${payment_amt:,.2f}")
    
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
    
    if not args.write:
        print(f"\n[DRY RUN] Would link {linked_count} Square refunds")
        print("Run with --write to apply changes")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
