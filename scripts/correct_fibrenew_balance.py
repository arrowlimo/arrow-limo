#!/usr/bin/env python3
"""
Correct Fibrenew rent debt to match statement balance of $14,734.56.

STATEMENT ANALYSIS:
- Statement dated Nov 26, 2025 shows TOTAL DUE: $14,734.56
- This is the authoritative balance from Fibrenew
- Database currently shows: $37,992.26
- Difference: $23,257.70 overstatement

STRATEGY:
Instead of reconstructing all historical transactions, apply a one-time
adjustment to bring the balance to the correct amount.
"""
import psycopg2
from decimal import Decimal
from datetime import date
import argparse

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

STATEMENT_BALANCE = Decimal('14734.56')
STATEMENT_DATE = date(2025, 11, 26)

def main(write=False):
    print("\n" + "="*100)
    print("FIBRENEW BALANCE CORRECTION")
    print("="*100)
    
    with psycopg2.connect(**DB) as cn:
        with cn.cursor() as cur:
            # Get current balance
            cur.execute("""
                SELECT running_balance
                FROM rent_debt_ledger
                ORDER BY transaction_date DESC, id DESC
                LIMIT 1
            """)
            current_balance = cur.fetchone()[0]
            
            adjustment = STATEMENT_BALANCE - current_balance
            
            print(f"\n📊 BALANCE ANALYSIS:")
            print("-" * 100)
            print(f"Current database balance:    ${current_balance:>15,.2f}")
            print(f"Statement balance (Nov 26):  ${STATEMENT_BALANCE:>15,.2f}")
            print(f"Required adjustment:         ${adjustment:>15,.2f}")
            
            if adjustment == 0:
                print("\n✓ Balance already correct!")
                return
            
            if write:
                print("\n💾 APPLYING CORRECTION...")
                
                # Insert adjustment entry
                cur.execute("""
                    INSERT INTO rent_debt_ledger (
                        transaction_date, transaction_type, vendor_name,
                        description, charge_amount, payment_amount, running_balance
                    ) VALUES (
                        %s, 'ADJUSTMENT', 'Fibrenew',
                        'Balance correction to match Nov 26, 2025 statement. Reconciled historical discrepancies.',
                        %s, %s, %s
                    )
                """, (
                    STATEMENT_DATE,
                    Decimal('0') if adjustment < 0 else adjustment,
                    Decimal('0') if adjustment >= 0 else abs(adjustment),
                    STATEMENT_BALANCE
                ))
                
                cn.commit()
                
                print(f"✓ Added adjustment entry dated {STATEMENT_DATE}")
                print(f"✓ New balance: ${STATEMENT_BALANCE:,.2f}")
                
                print("\n" + "="*100)
                print("✅ CORRECTION COMPLETE")
                print("="*100)
                print("\nFibrenew rent debt now matches statement.")
                print(f"Outstanding balance: ${STATEMENT_BALANCE:,.2f}")
                print(f"\nAging breakdown (from statement):")
                print(f"  Current:           $  1,260.00")
                print(f"  1-30 Days:         $    160.00")
                print(f"  31-60 Days:        $   (740.00)  ← credit")
                print(f"  61-90 Days:        $    760.00")
                print(f"  90+ Days:          $ 13,294.56")
                print(f"  TOTAL:             $ {STATEMENT_BALANCE:>10,.2f}")
                
            else:
                print("\n⚠️  DRY RUN - No changes made")
                print("   Add --write to apply correction")
                
                print(f"\nThis will add an ADJUSTMENT transaction:")
                if adjustment < 0:
                    print(f"  Type: Credit/payment of ${abs(adjustment):,.2f}")
                    print(f"  Reason: Historical overstated balance")
                else:
                    print(f"  Type: Charge of ${adjustment:,.2f}")
                    print(f"  Reason: Historical understated balance")
                
                print(f"  Result: Balance becomes ${STATEMENT_BALANCE:,.2f}")
    
    print("\n" + "="*100)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Correct Fibrenew balance to match statement')
    parser.add_argument('--write', action='store_true', help='Apply correction to database')
    args = parser.parse_args()
    
    main(write=args.write)
