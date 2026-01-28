"""
Fibrenew Debt Status Report - Current Position

Shows:
1. Opening balance from historical statement
2. All charges and payments since Jan 2019
3. Current outstanding balance
4. GST components (included in amounts, not added)
"""
import psycopg2
from decimal import Decimal

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        # Get opening balance
        cur.execute("""
            SELECT transaction_date, charge_amount, running_balance, description
            FROM rent_debt_ledger
            WHERE transaction_type = 'opening_balance'
            ORDER BY transaction_date
            LIMIT 1
        """)
        opening = cur.fetchone()
        
        # Get summary totals
        cur.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE transaction_type = 'CHARGE') as charge_count,
                SUM(charge_amount) as total_charges,
                COUNT(*) FILTER (WHERE transaction_type = 'PAYMENT') as payment_count,
                SUM(payment_amount) as total_payments,
                MAX(running_balance) as final_balance
            FROM rent_debt_ledger
            WHERE transaction_type IN ('CHARGE', 'PAYMENT')
        """)
        charges_cnt, charges_tot, payments_cnt, payments_tot, final_bal = cur.fetchone()
        
        # Get most recent transactions
        cur.execute("""
            SELECT transaction_date, transaction_type, charge_amount, payment_amount, running_balance
            FROM rent_debt_ledger
            WHERE transaction_type IN ('CHARGE', 'PAYMENT')
            ORDER BY transaction_date DESC, id DESC
            LIMIT 10
        """)
        recent = cur.fetchall()
        
        print("\n" + "="*100)
        print("FIBRENEW RENT DEBT STATUS REPORT")
        print("="*100)
        
        if opening:
            print(f"\nOPENING BALANCE (as of {opening[0]}):")
            print(f"  Amount: ${opening[1]:,.2f}")
            print(f"  Source: {opening[3][:80]}...")
        
        print(f"\nACTIVITY SUMMARY (Jan 2019 - Present):")
        print(f"  Monthly charges: {charges_cnt or 0} @ $682.50/month")
        print(f"  Total charged: ${charges_tot or 0:,.2f}")
        print(f"  Payments made: {payments_cnt or 0}")
        print(f"  Total paid: ${payments_tot or 0:,.2f}")
        print(f"  Current balance: ${final_bal or 0:,.2f}")
        
        if opening:
            total_debt = (opening[1] or Decimal('0')) + (charges_tot or Decimal('0'))
            print(f"\nDEBT RECONCILIATION:")
            print(f"  Opening balance:     ${opening[1]:>12,.2f}")
            print(f"  + New charges:       ${charges_tot or 0:>12,.2f}")
            print(f"  = Total owed:        ${total_debt:>12,.2f}")
            print(f"  - Payments made:     ${payments_tot or 0:>12,.2f}")
            print(f"  = Outstanding:       ${total_debt - (payments_tot or Decimal('0')):>12,.2f}")
        
        print(f"\nMOST RECENT ACTIVITY (last 10 transactions):")
        print(f"  {'Date':<12} {'Type':<10} {'Charge':>12} {'Payment':>12} {'Balance':>12}")
        print("  " + "-"*70)
        for row in recent:
            print(f"  {row[0]!s:<12} {row[1]:<10} ${row[2] or 0:>10,.2f} ${row[3] or 0:>10,.2f} ${row[4]:>10,.2f}")
        
        print("\n" + "="*100)
        print("NOTE: All amounts are GST-INCLUDED (not added on top).")
        print("      $682.50 monthly rent = $650.00 net + $32.50 GST (5% AB rate)")
        print("="*100)
