#!/usr/bin/env python3
"""
Fix Fibrenew rent charges to reflect actual rent increases:
- Oct 2024 - July 2025: $1,102.50/month (was $682.50)
- Aug 2025 onwards: $1,260.00/month (was $682.50)

This will reduce the outstanding balance from $37,992.26 to match
the statement's $14,734.56.
"""
import psycopg2
from decimal import Decimal
import argparse

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

# Rent increase schedule
OLD_RENT = Decimal('682.50')
RENT_PHASE_1 = Decimal('1102.50')  # Oct 2024 - July 2025
RENT_PHASE_2 = Decimal('1260.00')  # Aug 2025 onwards

from datetime import date

PHASE_1_START = date(2024, 10, 1)
PHASE_2_START = date(2025, 8, 1)

def main(write=False):
    print("\n" + "="*100)
    print("FIBRENEW RENT INCREASE CORRECTION")
    print("="*100)
    
    with psycopg2.connect(**DB) as cn:
        with cn.cursor() as cur:
            # Find charges that need updating
            cur.execute("""
                SELECT id, transaction_date, charge_amount, running_balance
                FROM rent_debt_ledger
                WHERE transaction_type = 'CHARGE'
                AND transaction_date >= %s
                ORDER BY transaction_date
            """, (PHASE_1_START,))
            
            charges_to_fix = cur.fetchall()
            
            print(f"\n📋 CHARGES TO UPDATE (since {PHASE_1_START}):")
            print("-" * 100)
            print(f"{'ID':<6} {'Date':<12} {'Current':>12} {'Correct':>12} {'Difference':>12}")
            print("-" * 100)
            
            total_adjustment = Decimal('0')
            updates = []
            
            for row_id, date, current_amt, running_bal in charges_to_fix:
                # Determine correct amount
                if date >= PHASE_2_START:
                    correct_amt = RENT_PHASE_2
                elif date >= PHASE_1_START:
                    correct_amt = RENT_PHASE_1
                else:
                    correct_amt = OLD_RENT
                
                diff = correct_amt - current_amt
                total_adjustment += diff
                
                print(f"{row_id:<6} {date!s:<12} ${current_amt:>10,.2f} ${correct_amt:>10,.2f} ${diff:>10,.2f}")
                
                updates.append((correct_amt, row_id))
            
            print("-" * 100)
            print(f"Total adjustment: ${total_adjustment:,.2f}")
            print(f"Charges to update: {len(updates)}")
            
            if write:
                print("\n💾 APPLYING UPDATES...")
                
                # Update charge amounts
                for correct_amt, row_id in updates:
                    cur.execute("""
                        UPDATE rent_debt_ledger
                        SET charge_amount = %s
                        WHERE id = %s
                    """, (correct_amt, row_id))
                
                print(f"✓ Updated {len(updates)} charge amounts")
                
                # Recalculate running balances
                print("\n🔄 RECALCULATING RUNNING BALANCES...")
                cur.execute("""
                    SELECT id, transaction_date, transaction_type, 
                           charge_amount, payment_amount, running_balance
                    FROM rent_debt_ledger
                    ORDER BY transaction_date, id
                """)
                
                all_txns = cur.fetchall()
                
                # Get opening balance from first row
                balance = all_txns[0][5] if all_txns and all_txns[0][2] == 'OPENING' else Decimal('16119.69')
                
                balance_updates = []
                
                for row_id, date, txn_type, charge, payment, old_balance in all_txns:
                    if txn_type == 'OPENING':
                        continue
                    
                    balance += (charge or 0) - (payment or 0)
                    balance_updates.append((balance, row_id))
                
                # Apply running balance updates
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
                    ORDER BY transaction_date DESC, ledger_id DESC
                    LIMIT 1
                """)
                final_balance = cur.fetchone()[0]
                
                print("\n" + "="*100)
                print("✅ UPDATE COMPLETE")
                print("="*100)
                print(f"New outstanding balance: ${final_balance:,.2f}")
                print(f"Statement shows: $14,734.56")
                print(f"Difference: ${abs(final_balance - Decimal('14734.56')):,.2f}")
                
            else:
                print("\n⚠️  DRY RUN - No changes made")
                print("   Add --write to apply changes")
                
                # Estimate what final balance would be
                estimated_reduction = total_adjustment
                current_balance = Decimal('37992.26')
                estimated_new = current_balance + estimated_reduction
                
                print(f"\nEstimated new balance: ${estimated_new:,.2f}")
                print(f"Statement shows: $14,734.56")
                print(f"Estimated difference: ${abs(estimated_new - Decimal('14734.56')):,.2f}")
    
    print("\n" + "="*100)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fix Fibrenew rent increases')
    parser.add_argument('--write', action='store_true', help='Apply changes to database')
    args = parser.parse_args()
    
    main(write=args.write)
