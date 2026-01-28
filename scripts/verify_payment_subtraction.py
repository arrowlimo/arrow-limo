"""
Verify how Fibrenew payments flow through the ledger system
"""
import psycopg2
from decimal import Decimal

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        # Check a few payment transactions to see how they affect running_balance
        cur.execute("""
            SELECT transaction_date, transaction_type, charge_amount, payment_amount, 
                   running_balance, description
            FROM rent_debt_ledger
            WHERE transaction_type = 'PAYMENT'
            ORDER BY transaction_date DESC
            LIMIT 5
        """)
        
        print("RECENT PAYMENT TRANSACTIONS:")
        print("="*120)
        print(f"{'Date':<12} {'Type':<12} {'Charge':>12} {'Payment':>12} {'Balance After':>15} {'Description':<40}")
        print("-"*120)
        
        for row in cur.fetchall():
            print(f"{row[0]!s:<12} {row[1]:<12} ${row[2] or 0:>10,.2f} ${row[3] or 0:>10,.2f} ${row[4]:>13,.2f} {row[5][:40]}")
        
        # Get a sequence showing charge → payment → charge to see the pattern
        print("\n\nSAMPLE SEQUENCE (Charge → Payment → Charge):")
        print("="*120)
        cur.execute("""
            SELECT transaction_date, transaction_type, charge_amount, payment_amount, running_balance
            FROM rent_debt_ledger
            WHERE transaction_date BETWEEN '2025-07-01' AND '2025-08-15'
            ORDER BY transaction_date, id
        """)
        
        prev_balance = None
        for row in cur.fetchall():
            balance_change = ""
            if prev_balance is not None:
                change = row[4] - prev_balance
                balance_change = f"(change: {'+' if change >= 0 else ''}{change:,.2f})"
            
            print(f"{row[0]!s:<12} {row[1]:<12} charge=${row[2] or 0:>8,.2f} payment=${row[3] or 0:>8,.2f} → balance=${row[4]:>10,.2f} {balance_change}")
            prev_balance = row[4]
        
        # Calculate expected vs actual
        print("\n\nVERIFICATION:")
        print("="*120)
        cur.execute("""
            SELECT 
                SUM(charge_amount) as total_charges,
                SUM(payment_amount) as total_payments,
                MAX(running_balance) as final_balance
            FROM rent_debt_ledger
            WHERE transaction_type IN ('CHARGE', 'PAYMENT')
        """)
        charges, payments, final = cur.fetchone()
        
        cur.execute("""
            SELECT charge_amount FROM rent_debt_ledger WHERE transaction_type = 'opening_balance'
        """)
        opening = cur.fetchone()
        opening_amt = opening[0] if opening else Decimal('0')
        
        expected = opening_amt + charges - payments
        
        print(f"Opening balance:     ${opening_amt:>12,.2f}")
        print(f"+ Total charges:     ${charges:>12,.2f}")
        print(f"- Total payments:    ${payments:>12,.2f}")
        print(f"= Expected balance:  ${expected:>12,.2f}")
        print(f"  Actual balance:    ${final:>12,.2f}")
        print(f"  Difference:        ${expected - final:>12,.2f}")
