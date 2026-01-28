#!/usr/bin/env python3
"""
Add missing Fibrenew payments from statement to database.
Missing payments (from screenshot comparison):
- 2025-05-14: $1,102.50
- 2025-07-04: $400.00 (second payment same day - database only has $800)
- 2025-09-16: $500.00
- 2025-10-02: $2,000.00
- 2025-11-10: $900.00
- 2025-11-17: $200.00
"""
import psycopg2
from decimal import Decimal
from datetime import date
import argparse

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

missing_payments = [
    (date(2025, 5, 14), Decimal('1102.50'), 'Missing May payment'),
    (date(2025, 7, 4), Decimal('400.00'), 'Second payment same day (first $800 already recorded)'),
    (date(2025, 9, 16), Decimal('500.00'), 'September payment'),
    (date(2025, 10, 2), Decimal('2000.00'), 'October payment'),
    (date(2025, 11, 10), Decimal('900.00'), 'November payment #9/100'),
    (date(2025, 11, 17), Decimal('200.00'), 'November payment'),
]

def main(write=False):
    print("\n" + "="*100)
    print("ADD MISSING FIBRENEW PAYMENTS")
    print("="*100)
    
    total_missing = sum(amt for dt, amt, desc in missing_payments)
    
    print(f"\n📋 MISSING PAYMENTS TO ADD:")
    print("-" * 100)
    print(f"{'Date':<12} {'Amount':>12} {'Description':<60}")
    print("-" * 100)
    
    for dt, amt, desc in missing_payments:
        print(f"{dt!s:<12} ${amt:>10,.2f} {desc:<60}")
    
    print("-" * 100)
    print(f"Total missing: ${total_missing:,.2f}")
    
    if write:
        with psycopg2.connect(**DB) as cn:
            with cn.cursor() as cur:
                print("\n💾 ADDING PAYMENTS...")
                
                for payment_date, amount, description in missing_payments:
                    # Insert payment
                    cur.execute("""
                        INSERT INTO rent_debt_ledger (
                            transaction_date, transaction_type, vendor_name,
                            description, payment_amount
                        ) VALUES (%s, 'PAYMENT', 'Fibrenew', %s, %s)
                    """, (payment_date, description, amount))
                    
                    print(f"  ✓ Added {payment_date}: ${amount:,.2f}")
                
                # Recalculate running balances
                print("\n🔄 RECALCULATING RUNNING BALANCES...")
                
                cur.execute("""
                    SELECT id, transaction_date, transaction_type, 
                           charge_amount, payment_amount, running_balance
                    FROM rent_debt_ledger
                    ORDER BY transaction_date, id
                """)
                
                all_txns = cur.fetchall()
                
                # Get opening balance
                balance = all_txns[0][5] if all_txns and all_txns[0][2] == 'OPENING' else Decimal('16119.69')
                
                balance_updates = []
                
                for row_id, txn_date, txn_type, charge, payment, old_balance in all_txns:
                    if txn_type == 'OPENING':
                        continue
                    
                    balance += (charge or 0) - (payment or 0)
                    balance_updates.append((balance, row_id))
                
                # Apply updates
                for new_balance, row_id in balance_updates:
                    cur.execute("""
                        UPDATE rent_debt_ledger
                        SET running_balance = %s
                        WHERE id = %s
                    """, (new_balance, row_id))
                
                print(f"✓ Recalculated {len(balance_updates)} running balances")
                
                cn.commit()
                
                # Show new final balance
                cur.execute("""
                    SELECT running_balance
                    FROM rent_debt_ledger
                    ORDER BY transaction_date DESC, id DESC
                    LIMIT 1
                """)
                final_balance = cur.fetchone()[0]
                
                print("\n" + "="*100)
                print("✅ UPDATE COMPLETE")
                print("="*100)
                print(f"Old balance: $37,992.26")
                print(f"Payments added: ${total_missing:,.2f}")
                print(f"New balance: ${final_balance:,.2f}")
                print(f"Statement shows: $14,734.56")
                print(f"Remaining difference: ${abs(final_balance - Decimal('14734.56')):,.2f}")
    else:
        print("\n⚠️  DRY RUN - No changes made")
        print("   Add --write to apply changes")
        print(f"\nEstimated new balance: ${Decimal('37992.26') - total_missing:,.2f}")
        print(f"Statement shows: $14,734.56")
    
    print("\n" + "="*100)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Add missing Fibrenew payments')
    parser.add_argument('--write', action='store_true', help='Apply changes to database')
    args = parser.parse_args()
    
    main(write=args.write)
