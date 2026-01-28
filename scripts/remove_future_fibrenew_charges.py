#!/usr/bin/env python3
"""
Remove future charges after the statement date (Nov 26, 2025).
The statement balance is as of Nov 26, so charges dated Dec 1 or later
should not exist yet.
"""
import psycopg2
from datetime import date
import argparse

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

STATEMENT_DATE = date(2025, 11, 26)

def main(write=False):
    print("\n" + "="*100)
    print("REMOVE FUTURE FIBRENEW CHARGES")
    print("="*100)
    
    with psycopg2.connect(**DB) as cn:
        with cn.cursor() as cur:
            # Find charges after statement date
            cur.execute("""
                SELECT id, transaction_date, charge_amount, running_balance
                FROM rent_debt_ledger
                WHERE transaction_type = 'CHARGE'
                AND transaction_date > %s
                ORDER BY transaction_date
            """, (STATEMENT_DATE,))
            
            future_charges = cur.fetchall()
            
            if not future_charges:
                print("\n✓ No future charges found")
                return
            
            print(f"\n⚠️  CHARGES AFTER STATEMENT DATE ({STATEMENT_DATE}):")
            print("-" * 100)
            print(f"{'ID':<6} {'Date':<12} {'Amount':>12} {'Running Balance':>15}")
            print("-" * 100)
            
            for row_id, dt, amt, bal in future_charges:
                print(f"{row_id:<6} {dt!s:<12} ${amt:>10,.2f} ${bal:>12,.2f}")
            
            print(f"\nTotal charges to remove: {len(future_charges)}")
            
            if write:
                print("\n💾 DELETING FUTURE CHARGES...")
                
                cur.execute("""
                    DELETE FROM rent_debt_ledger
                    WHERE transaction_type = 'CHARGE'
                    AND transaction_date > %s
                """, (STATEMENT_DATE,))
                
                deleted = cur.rowcount
                cn.commit()
                
                print(f"✓ Deleted {deleted} future charge(s)")
                
                # Check final balance
                cur.execute("""
                    SELECT running_balance
                    FROM rent_debt_ledger
                    ORDER BY transaction_date DESC, id DESC
                    LIMIT 1
                """)
                final_balance = cur.fetchone()[0]
                
                print(f"\n✅ Final balance: ${final_balance:,.2f}")
                print(f"   Should be: $14,734.56")
                
                if abs(final_balance - 14734.56) < 0.01:
                    print("   ✅ MATCHES STATEMENT!")
                else:
                    print("   ⚠️  Still doesn't match")
            else:
                print("\n⚠️  DRY RUN - No changes made")
                print("   Add --write to delete these charges")
    
    print("\n" + "="*100)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Remove future Fibrenew charges')
    parser.add_argument('--write', action='store_true', help='Apply deletion')
    args = parser.parse_args()
    
    main(write=args.write)
