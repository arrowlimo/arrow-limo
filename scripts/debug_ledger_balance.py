"""
Debug the ledger balance calculation issue
"""
import psycopg2

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        # Check first 10 transactions chronologically
        cur.execute("""
            SELECT id, transaction_date, transaction_type, charge_amount, payment_amount, running_balance
            FROM rent_debt_ledger
            ORDER BY transaction_date, id
            LIMIT 15
        """)
        
        print("FIRST 15 LEDGER ENTRIES (chronological):")
        print("="*100)
        print(f"{'ID':<6} {'Date':<12} {'Type':<18} {'Charge':>12} {'Payment':>12} {'Balance':>12}")
        print("-"*100)
        
        for row in cur.fetchall():
            print(f"{row[0]:<6} {row[1]!s:<12} {row[2]:<18} ${row[3] or 0:>10,.2f} ${row[4] or 0:>10,.2f} ${row[5]:>10,.2f}")
        
        # The problem: regular CHARGE entries have their own running_balance
        # that doesn't start from opening_balance
        print("\n\nISSUE IDENTIFIED:")
        print("="*100)
        print("The regular CHARGE/PAYMENT entries have running_balance calculated separately")
        print("from the opening_balance entry. The opening_balance is an isolated entry.")
        print("\nThe rent_debt_ledger needs to be rebuilt with opening balance as the starting point.")
