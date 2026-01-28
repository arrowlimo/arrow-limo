#!/usr/bin/env python3
"""
Work backwards from statement balance to determine correct opening balance.

Statement final balance: $14,734.56 as of Nov 17, 2025
"""
import psycopg2
from decimal import Decimal

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

# From screenshot - ALL transactions visible (extending the earlier partial list)
# These are charges at $1,102.50 (Oct 2024-July 2025) and $1,260.00 (Aug 2025+)
statement_charges_2024_2025 = Decimal('1102.50') * 10 + Decimal('1260.00') * 5  # Oct 2024 through Nov 2025

# From screenshot - ALL payments visible
statement_payments_2024_2025 = (
    Decimal('1000.00') +    # Oct 19, 2024
    Decimal('1102.50') +    # Nov 4, 2024
    Decimal('1500.00') +    # Dec 5, 2024
    Decimal('1200.00') +    # Jan 7, 2025
    Decimal('1102.50') +    # Feb 4, 2025
    Decimal('1102.50') +    # Mar 10, 2025
    Decimal('1102.50') +    # Apr 8, 2025
    Decimal('1102.50') +    # May 14, 2025
    Decimal('1102.50') +    # Jun 10, 2025
    Decimal('800.00') +     # Jul 4, 2025
    Decimal('400.00') +     # Jul 4, 2025 (second payment)
    Decimal('2500.00') +    # Jul 31, 2025
    Decimal('300.00') +     # Aug 15, 2025
    Decimal('500.00') +     # Sep 16, 2025
    Decimal('2000.00') +    # Oct 2, 2025
    Decimal('900.00') +     # Nov 10, 2025
    Decimal('200.00')       # Nov 17, 2025
)

print("\n" + "="*100)
print("WORKING BACKWARDS FROM STATEMENT")
print("="*100)

print(f"\nStatement final balance (Nov 17, 2025): ${Decimal('14734.56'):,.2f}")
print(f"\nCharges Oct 2024 - Nov 2025:")
print(f"  10 months @ $1,102.50 = ${Decimal('1102.50') * 10:,.2f}")
print(f"   5 months @ $1,260.00 = ${Decimal('1260.00') * 5:,.2f}")
print(f"  Total charges = ${statement_charges_2024_2025:,.2f}")

print(f"\nPayments Oct 2024 - Nov 2025: ${statement_payments_2024_2025:,.2f}")

# Calculate what balance was before Oct 2024
balance_before_oct_2024 = Decimal('14734.56') - statement_charges_2024_2025 + statement_payments_2024_2025

print(f"\nBalance before Oct 2024 must have been:")
print(f"  ${Decimal('14734.56'):,.2f} (final) - ${statement_charges_2024_2025:,.2f} (charges) + ${statement_payments_2024_2025:,.2f} (payments)")
print(f"  = ${balance_before_oct_2024:,.2f}")

with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        # What does database show for Sept 2024?
        cur.execute("""
            SELECT running_balance
            FROM rent_debt_ledger
            WHERE transaction_date = '2024-09-01'
            AND transaction_type = 'CHARGE'
        """)
        db_sept_2024 = cur.fetchone()
        if db_sept_2024:
            print(f"\nDatabase balance after Sept 2024 charge: ${db_sept_2024[0]:,.2f}")
            print(f"Difference: ${db_sept_2024[0] - balance_before_oct_2024:,.2f}")
        
        # Check opening balance in database
        cur.execute("""
            SELECT running_balance
            FROM rent_debt_ledger
            WHERE transaction_type = 'OPENING'
        """)
        db_opening = cur.fetchone()
        if db_opening:
            print(f"\nDatabase opening balance: ${db_opening[0]:,.2f}")
            
            # Calculate all charges and payments from opening to Sept 2024
            cur.execute("""
                SELECT 
                    SUM(CASE WHEN transaction_type = 'CHARGE' THEN charge_amount ELSE 0 END) as charges,
                    SUM(CASE WHEN transaction_type = 'PAYMENT' THEN payment_amount ELSE 0 END) as payments
                FROM rent_debt_ledger
                WHERE transaction_date < '2024-10-01'
            """)
            pre_oct_charges, pre_oct_payments = cur.fetchone()
            
            calculated_sept_balance = db_opening[0] + pre_oct_charges - pre_oct_payments
            
            print(f"\nCalculation check:")
            print(f"  Opening: ${db_opening[0]:,.2f}")
            print(f"  + Charges before Oct 2024: ${pre_oct_charges:,.2f}")
            print(f"  - Payments before Oct 2024: ${pre_oct_payments:,.2f}")
            print(f"  = ${calculated_sept_balance:,.2f}")
            
            # What should opening balance be?
            correct_opening = balance_before_oct_2024 - pre_oct_charges + pre_oct_payments
            print(f"\nCORRECT opening balance should be:")
            print(f"  ${balance_before_oct_2024:,.2f} (Sept 2024 target) - ${pre_oct_charges:,.2f} (charges) + ${pre_oct_payments:,.2f} (payments)")
            print(f"  = ${correct_opening:,.2f}")
            print(f"\nDifference from current: ${correct_opening - db_opening[0]:,.2f}")

print("\n" + "="*100)
