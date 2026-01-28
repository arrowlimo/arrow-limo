#!/usr/bin/env python3
"""
Match Square payments to LMS payment totals (aggregated by PaymentID).

LMS often records one payment split across multiple charters.
This finds Square payments where the amount matches an LMS PaymentID total.

Usage:
  python -X utf8 scripts/match_square_to_lms_payment_totals.py         # dry run
  python -X utf8 scripts/match_square_to_lms_payment_totals.py --write # apply
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_PORT = int(os.getenv("DB_PORT", "5432"))

def main():
    write = '--write' in sys.argv
    
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get unmatched Square payments
    cur.execute("""
        SELECT payment_id, amount, payment_date, payment_key, square_payment_id
        FROM payments
        WHERE payment_method = 'credit_card'
          AND payment_key IS NOT NULL
          AND charter_id IS NULL
        ORDER BY amount DESC
    """)
    square_payments = cur.fetchall()
    
    if not square_payments:
        print("✓ All Square payments are matched")
        return
    
    print(f"Found {len(square_payments)} unmatched Square payments")
    print(f"Total: ${sum(float(p['amount']) for p in square_payments):,.2f}\n")
    
    # Get LMS payment totals grouped by PaymentID
    cur.execute("""
        SELECT payment_id, 
               SUM(payment_amount) as total_amount,
               COUNT(*) as charter_count,
               STRING_AGG(reserve_no, ', ' ORDER BY reserve_no) as reserve_numbers
        FROM lms_unified_map
        WHERE payment_id IS NOT NULL
        GROUP BY payment_id
        HAVING COUNT(*) > 1  -- Only multi-charter payments
        ORDER BY payment_id
    """)
    lms_payment_totals = cur.fetchall()
    
    print(f"LMS multi-charter payments: {len(lms_payment_totals)}\n")
    
    # Build lookup by amount (rounded to cents)
    lms_by_amount = defaultdict(list)
    for lms in lms_payment_totals:
        amt = round(float(lms['total_amount']), 2)
        lms_by_amount[amt].append(lms)
    
    # Match Square to LMS payment totals
    matches = []
    for sq in square_payments:
        sq_amt = round(float(sq['amount']), 2)
        
        # Exact match
        if sq_amt in lms_by_amount:
            for lms in lms_by_amount[sq_amt]:
                matches.append({
                    'square_payment_id': sq['payment_id'],
                    'square_amount': sq_amt,
                    'lms_payment_id': lms['payment_id'],
                    'lms_total': round(float(lms['total_amount']), 2),
                    'charter_count': lms['charter_count'],
                    'reserves': lms['reserve_numbers'],
                    'match_type': 'exact'
                })
        
        # ~1% tolerance match
        else:
            for amt in lms_by_amount:
                if abs(amt - sq_amt) / max(sq_amt, 0.01) <= 0.01:
                    for lms in lms_by_amount[amt]:
                        matches.append({
                            'square_payment_id': sq['payment_id'],
                            'square_amount': sq_amt,
                            'lms_payment_id': lms['payment_id'],
                            'lms_total': round(float(lms['total_amount']), 2),
                            'charter_count': lms['charter_count'],
                            'reserves': lms['reserve_numbers'],
                            'match_type': '~1%'
                        })
    
    if not matches:
        print("No Square payments match LMS multi-charter payment totals")
        return
    
    print(f"Found {len(matches)} Square → LMS payment total matches:\n")
    
    # Group by LMS payment to handle duplicates
    applied = 0
    for i, m in enumerate(matches, 1):
        reserves = m['reserves'].split(', ')
        print(f"{i}. Square payment {m['square_payment_id']}: ${m['square_amount']:,.2f}")
        print(f"   LMS Payment {m['lms_payment_id']}: ${m['lms_total']:,.2f} split across {m['charter_count']} charters")
        print(f"   Reserves: {m['reserves']}")
        print(f"   Match: {m['match_type']}")
        
        if write:
            # Get charter_ids for these reserves
            cur.execute("""
                SELECT charter_id, reserve_number 
                FROM charters 
                WHERE reserve_number = ANY(%s)
                ORDER BY reserve_number
            """, (reserves,))
            
            charters = cur.fetchall()
            
            if charters:
                # Link to first charter, note the split in notes
                primary_charter = charters[0]
                all_reserves = ', '.join([c['reserve_number'] for c in charters])
                
                cur.execute("""
                    UPDATE payments
                    SET charter_id = %s,
                        reserve_number = %s,
                        notes = COALESCE(notes, '') || %s,
                        last_updated = NOW()
                    WHERE payment_id = %s
                """, (
                    primary_charter['charter_id'],
                    primary_charter['reserve_number'],
                    f" [SPLIT-PAYMENT: LMS Payment {m['lms_payment_id']} split across reserves: {all_reserves}]",
                    m['square_payment_id']
                ))
                
                # Recalculate balances for all affected charters
                for charter in charters:
                    cur.execute("""
                        WITH payment_sum AS (
                            SELECT COALESCE(SUM(amount), 0) AS total_paid
                            FROM payments
                            WHERE reserve_number = %s
                        )
                        UPDATE charters AS c
                        SET paid_amount = ps.total_paid,
                            balance = COALESCE(total_amount_due, 0) - ps.total_paid,
                            updated_at = NOW()
                        FROM payment_sum ps
                        WHERE c.reserve_number = %s
                    """, (charter['reserve_number'], charter['reserve_number']))
                
                applied += 1
                print(f"   ✓ Linked to charter {primary_charter['charter_id']} (reserve {primary_charter['reserve_number']})")
            else:
                print(f"   ⚠️ No charters found for reserves")
        else:
            print(f"   Would link to first reserve's charter")
        
        print()
    
    if write:
        conn.commit()
        print(f"\n✓ COMMITTED: Applied {applied} split-payment matches")
    else:
        print(f"\nDRY RUN: Would apply {len(matches)} matches")
        print("Run with --write to apply")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
