#!/usr/bin/env python3
"""
Verify Fibrenew statement balances match the PDF screenshot.
Compare running balance after each transaction to ensure consistency.
"""
import psycopg2
from decimal import Decimal
from datetime import date

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

# From screenshot - the statement shows final balance of $14,734.56
STATEMENT_FINAL_BALANCE = Decimal('14734.56')

print("\n" + "="*100)
print("FIBRENEW STATEMENT BALANCE VERIFICATION")
print("="*100)

with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        # Get ALL transactions in chronological order
        cur.execute("""
            SELECT id, transaction_date, transaction_type, charge_amount, payment_amount, 
                   running_balance, description
            FROM rent_debt_ledger
            ORDER BY transaction_date, id
        """)
        
        all_txns = cur.fetchall()
        
        print(f"\nTotal transactions in ledger: {len(all_txns)}")
        
        # Verify running balance calculations
        print("\nVERIFYING RUNNING BALANCE CALCULATIONS:")
        print("-" * 100)
        
        errors = []
        prev_balance = None
        
        for i, txn in enumerate(all_txns):
            txn_id, txn_date, txn_type, charge, payment, balance, desc = txn
            
            if i == 0:
                # First entry should set the opening balance
                if txn_type == 'opening_balance':
                    expected = charge or Decimal('0')
                    prev_balance = balance
                    if abs(balance - expected) > Decimal('0.01'):
                        errors.append({
                            'line': i+1,
                            'date': txn_date,
                            'type': txn_type,
                            'expected': expected,
                            'actual': balance,
                            'diff': balance - expected
                        })
                    continue
            
            # Calculate expected balance
            if txn_type == 'CHARGE':
                expected = prev_balance + (charge or Decimal('0'))
            elif txn_type == 'PAYMENT':
                expected = prev_balance - (payment or Decimal('0'))
            else:
                expected = balance  # Unknown type, accept stored value
            
            # Check if actual matches expected
            if abs(balance - expected) > Decimal('0.01'):
                errors.append({
                    'line': i+1,
                    'date': txn_date,
                    'type': txn_type,
                    'prev_balance': prev_balance,
                    'charge': charge,
                    'payment': payment,
                    'expected': expected,
                    'actual': balance,
                    'diff': balance - expected
                })
            
            prev_balance = balance
        
        if errors:
            print(f"\n⚠️  FOUND {len(errors)} BALANCE INCONSISTENCIES:\n")
            for err in errors[:20]:  # Show first 20
                print(f"Line {err['line']}: {err['date']} - {err['type']}")
                if 'prev_balance' in err:
                    print(f"  Previous: ${err['prev_balance']:,.2f}")
                    if err.get('charge'):
                        print(f"  + Charge: ${err['charge']:,.2f}")
                    if err.get('payment'):
                        print(f"  - Payment: ${err['payment']:,.2f}")
                print(f"  Expected: ${err['expected']:,.2f}")
                print(f"  Actual:   ${err['actual']:,.2f}")
                print(f"  Diff:     ${err['diff']:+,.2f}")
                print()
            
            if len(errors) > 20:
                print(f"... and {len(errors)-20} more errors")
        else:
            print("✓ All running balance calculations are correct")
        
        # Compare final balance to statement
        final_balance = all_txns[-1][5] if all_txns else Decimal('0')
        
        print("\n" + "="*100)
        print("FINAL BALANCE COMPARISON:")
        print("="*100)
        print(f"Statement shows (from PDF):  ${STATEMENT_FINAL_BALANCE:>12,.2f}")
        print(f"Database calculates:         ${final_balance:>12,.2f}")
        print(f"Difference:                  ${final_balance - STATEMENT_FINAL_BALANCE:>12,.2f}")
        
        if abs(final_balance - STATEMENT_FINAL_BALANCE) < Decimal('0.01'):
            print("\n✓ BALANCES MATCH!")
        else:
            print("\n⚠️  BALANCES DO NOT MATCH")
            print("\nPossible causes:")
            print("1. Missing charges or payments in database")
            print("2. Incorrect opening balance")
            print("3. Statement includes transactions not yet in database")
            print("4. Calculation error in running balance")
        
        # Show last 10 transactions
        print("\n" + "="*100)
        print("LAST 10 TRANSACTIONS IN DATABASE:")
        print("="*100)
        print(f"{'Date':<12} {'Type':<15} {'Charge':>12} {'Payment':>12} {'Balance':>12}")
        print("-" * 100)
        
        for txn in all_txns[-10:]:
            txn_id, txn_date, txn_type, charge, payment, balance, desc = txn
            print(f"{txn_date!s:<12} {txn_type:<15} ${charge or 0:>10,.2f} ${payment or 0:>10,.2f} ${balance:>10,.2f}")

print("\n" + "="*100)
