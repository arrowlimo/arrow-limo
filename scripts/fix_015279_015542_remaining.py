#!/usr/bin/env python3
"""Fix 015279 and 015542 - delete remaining NULL-key duplicates and false credits.

These 2 reserves have:
  - 1 legitimate payment WITH payment_key
  - 1 NULL-key duplicate from 2025-08-05 that should be deleted
  - False credit ledger entries created from the duplicate

Actions:
  1. Delete NULL-key payments (29404, 29166)
  2. Delete false credit ledger entries
  3. Recalculate charter balances (should become -$500 matching LMS)
"""

import psycopg2
from argparse import ArgumentParser

def fix(dry_run=True):
    conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
    cur = conn.cursor()
    
    try:
        # Find NULL-key payments for these 2 reserves
        cur.execute("""
            SELECT payment_id, reserve_number, amount
            FROM payments
            WHERE reserve_number IN ('015279', '015542')
            AND payment_key IS NULL
            AND created_at::date = '2025-08-05'
        """)
        to_delete = cur.fetchall()
        
        print(f"Found {len(to_delete)} NULL-key duplicate payments:")
        for pid, reserve, amount in to_delete:
            print(f"  Payment {pid}: Reserve {reserve}, ${amount:.2f}")
        print()
        
        # Find false credits
        cur.execute("""
            SELECT credit_id, source_reserve_number, credit_amount
            FROM charter_credit_ledger
            WHERE source_reserve_number IN ('015279', '015542')
        """)
        false_credits = cur.fetchall()
        
        print(f"Found {len(false_credits)} false credit ledger entries:")
        for cid, reserve, amount in false_credits:
            print(f"  Credit {cid}: Reserve {reserve}, ${amount:.2f}")
        print()
        
        if dry_run:
            print("=== DRY-RUN MODE ===")
            print("Run with --write to execute fixes")
            return
        
        # Delete income_ledger entries
        payment_ids = [p[0] for p in to_delete]
        cur.execute("DELETE FROM income_ledger WHERE payment_id = ANY(%s)", (payment_ids,))
        income_deleted = cur.rowcount
        
        # Delete banking_payment_links
        cur.execute("DELETE FROM banking_payment_links WHERE payment_id = ANY(%s)", (payment_ids,))
        banking_deleted = cur.rowcount
        
        # Delete payments
        cur.execute("DELETE FROM payments WHERE payment_id = ANY(%s)", (payment_ids,))
        payments_deleted = cur.rowcount
        
        # Delete false credits
        credit_ids = [c[0] for c in false_credits]
        cur.execute("DELETE FROM charter_credit_ledger WHERE credit_id = ANY(%s)", (credit_ids,))
        credits_deleted = cur.rowcount
        
        # Recalculate charter balances
        for reserve in ['015279', '015542']:
            cur.execute("""
                WITH payment_sum AS (
                    SELECT COALESCE(SUM(amount), 0) as total
                    FROM payments WHERE reserve_number = %s
                )
                UPDATE charters
                SET paid_amount = (SELECT total FROM payment_sum),
                    balance = total_amount_due - (SELECT total FROM payment_sum)
                WHERE reserve_number = %s
            """, (reserve, reserve))
        
        conn.commit()
        
        print(f"✓ Deleted {income_deleted} income_ledger entries")
        print(f"✓ Deleted {banking_deleted} banking_payment_links entries")
        print(f"✓ Deleted {payments_deleted} duplicate payments")
        print(f"✓ Deleted {credits_deleted} false credit ledger entries")
        print(f"✓ Updated 2 charter balances")
        print()
        
        # Verify
        cur.execute("""
            SELECT reserve_number, total_amount_due, paid_amount, balance
            FROM charters WHERE reserve_number IN ('015279', '015542')
        """)
        print("Final charter balances:")
        for reserve, due, paid, balance in cur.fetchall():
            print(f"  {reserve}: Due=${due:.2f}, Paid=${paid:.2f}, Balance=${balance:.2f}")
    
    finally:
        cur.close()
        conn.close()


def main():
    parser = ArgumentParser(description='Fix 015279 and 015542 remaining duplicates')
    parser.add_argument('--write', action='store_true', help='Execute fixes')
    args = parser.parse_args()
    
    fix(dry_run=not args.write)


if __name__ == '__main__':
    main()
