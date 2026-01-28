#!/usr/bin/env python3
"""
Apply all Fibrenew corrections:
1. Add missing payments ($5,102.50)
2. Add shareholder journal entry credits ($2,205.00)
3. Update invoice amounts to match statement (Oct 2024+)
4. Recalculate running balances

Expected result: Balance should match statement $14,734.56
"""
import psycopg2
from decimal import Decimal
from datetime import date
import argparse

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

# Missing payments from statement comparison
missing_payments = [
    (date(2025, 5, 14), Decimal('1102.50'), 'Missing May payment'),
    (date(2025, 7, 4), Decimal('400.00'), 'Second payment same day'),
    (date(2025, 9, 16), Decimal('500.00'), 'September payment'),
    (date(2025, 10, 2), Decimal('2000.00'), 'October payment'),
    (date(2025, 11, 10), Decimal('900.00'), 'November payment #9/100'),
    (date(2025, 11, 17), Decimal('200.00'), 'November payment'),
]

# Shareholder journal entries (debt write-offs per statement)
journal_entries = [
    (date(2023, 7, 31), Decimal('1458.58'), 'Journal Entry #21: shareholders earning'),
    (date(2023, 7, 31), Decimal('746.42'), 'Journal Entry #22: shareholder wedding'),
]

# Invoice amount corrections (per statement)
invoice_updates = [
    # Oct 2024 - Jul 2025: $1,102.50
    (date(2024, 10, 1), Decimal('1102.50')),
    (date(2024, 11, 1), Decimal('1102.50')),
    (date(2024, 12, 1), Decimal('1102.50')),
    (date(2025, 1, 1), Decimal('1102.50')),
    (date(2025, 2, 1), Decimal('1102.50')),
    (date(2025, 3, 1), Decimal('1102.50')),
    (date(2025, 4, 1), Decimal('1102.50')),
    (date(2025, 5, 1), Decimal('1102.50')),
    (date(2025, 6, 1), Decimal('1102.50')),
    (date(2025, 7, 1), Decimal('1102.50')),
    # Aug 2025+: $1,260.00
    (date(2025, 8, 1), Decimal('1260.00')),
    (date(2025, 9, 1), Decimal('1260.00')),
    (date(2025, 10, 1), Decimal('1260.00')),
    (date(2025, 11, 1), Decimal('1260.00')),
    (date(2025, 12, 1), Decimal('1260.00')),
]

def main(write=False):
    print("\n" + "="*100)
    print("FIBRENEW COMPREHENSIVE CORRECTION")
    print("="*100)
    
    total_payments = sum(amt for dt, amt, desc in missing_payments)
    total_credits = sum(amt for dt, amt, desc in journal_entries)
    
    print(f"\n📋 CORRECTIONS TO APPLY:")
    print("-" * 100)
    print(f"1. Missing payments: ${total_payments:,.2f} ({len(missing_payments)} payments)")
    print(f"2. Shareholder credits: ${total_credits:,.2f} ({len(journal_entries)} journal entries)")
    print(f"3. Invoice amount updates: {len(invoice_updates)} charges")
    
    if write:
        with psycopg2.connect(**DB) as cn:
            with cn.cursor() as cur:
                print("\n💾 APPLYING CORRECTIONS...")
                
                # Step 1: Add missing payments
                print("\n1️⃣ Adding missing payments...")
                for payment_date, amount, description in missing_payments:
                    cur.execute("""
                        INSERT INTO rent_debt_ledger (
                            transaction_date, transaction_type, vendor_name,
                            description, payment_amount
                        ) VALUES (%s, 'PAYMENT', 'Fibrenew', %s, %s)
                    """, (payment_date, description, amount))
                    print(f"   ✓ {payment_date}: ${amount:,.2f} - {description}")
                
                # Step 2: Add shareholder journal entry credits
                print("\n2️⃣ Adding shareholder credits...")
                for entry_date, amount, description in journal_entries:
                    cur.execute("""
                        INSERT INTO rent_debt_ledger (
                            transaction_date, transaction_type, vendor_name,
                            description, payment_amount
                        ) VALUES (%s, 'PAYMENT', 'Fibrenew', %s, %s)
                    """, (entry_date, description, amount))
                    print(f"   ✓ {entry_date}: ${amount:,.2f} - {description}")
                
                # Step 3: Update invoice amounts
                print("\n3️⃣ Updating invoice amounts...")
                for invoice_date, correct_amount in invoice_updates:
                    cur.execute("""
                        UPDATE rent_debt_ledger
                        SET charge_amount = %s
                        WHERE transaction_date = %s
                        AND transaction_type = 'CHARGE'
                    """, (correct_amount, invoice_date))
                    if cur.rowcount > 0:
                        print(f"   ✓ {invoice_date}: ${correct_amount:,.2f}")
                
                # Step 4: Recalculate all running balances
                print("\n4️⃣ Recalculating running balances...")
                cur.execute("""
                    SELECT id, transaction_date, transaction_type, 
                           charge_amount, payment_amount
                    FROM rent_debt_ledger
                    ORDER BY transaction_date, id
                """)
                
                all_txns = cur.fetchall()
                
                # Get opening balance
                balance = Decimal('16119.69')  # Original opening
                for row_id, txn_date, txn_type, charge, payment in all_txns:
                    if txn_type == 'OPENING':
                        balance = charge or payment or balance
                        continue
                    
                    balance += (charge or 0) - (payment or 0)
                    
                    cur.execute("""
                        UPDATE rent_debt_ledger
                        SET running_balance = %s
                        WHERE id = %s
                    """, (balance, row_id))
                
                print(f"   ✓ Recalculated {len(all_txns)} running balances")
                
                cn.commit()
                
                # Show final result
                cur.execute("""
                    SELECT running_balance
                    FROM rent_debt_ledger
                    ORDER BY transaction_date DESC, id DESC
                    LIMIT 1
                """)
                final_balance = cur.fetchone()[0]
                
                print("\n" + "="*100)
                print("✅ CORRECTIONS COMPLETE")
                print("="*100)
                print(f"Old database balance: $37,992.26")
                print(f"Corrections applied:")
                print(f"  - Payments: -${total_payments:,.2f}")
                print(f"  - Credits:  -${total_credits:,.2f}")
                print(f"  - Invoice updates: (affects running calc)")
                print(f"\nNew database balance: ${final_balance:,.2f}")
                print(f"Statement shows: $14,734.56")
                print(f"Difference: ${abs(final_balance - Decimal('14734.56')):,.2f}")
                
                if abs(final_balance - Decimal('14734.56')) < 100:
                    print("\n✅ BALANCES MATCH (within $100 tolerance)")
                else:
                    print("\n⚠️ Still have a discrepancy to investigate")
    
    else:
        print("\n⚠️  DRY RUN - No changes made")
        print("   Add --write to apply changes")
        
        estimated_new = Decimal('37992.26') - total_payments - total_credits
        print(f"\nEstimated new balance: ${estimated_new:,.2f}")
        print(f"Statement shows: $14,734.56")
        print(f"Estimated remaining difference: ${abs(estimated_new - Decimal('14734.56')):,.2f}")
        print("\nNote: Invoice amount updates will further adjust the balance")
    
    print("\n" + "="*100)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Apply all Fibrenew corrections')
    parser.add_argument('--write', action='store_true', help='Apply changes to database')
    args = parser.parse_args()
    
    main(write=args.write)
