#!/usr/bin/env python
import psycopg2

c = psycopg2.connect('dbname=almsdata user=postgres password=***REMOVED***')
r = c.cursor()

print("Payroll account details:\n")
for acct in ['1085 Payroll Clearing Account', '2100 Payroll Liabilities', '6605 Payroll Expenses']:
    r.execute("""
        SELECT 
            COUNT(*), 
            SUM(COALESCE(debit,0)), 
            SUM(COALESCE(credit,0)),
            SUM(COALESCE(credit,0) - COALESCE(debit,0))
        FROM general_ledger 
        WHERE account = %s
    """, (acct,))
    cnt, dr, cr, net = r.fetchone()
    print(f"{acct}")
    print(f"  Transactions: {cnt:,}")
    print(f"  Debits:  ${dr:,.2f}")
    print(f"  Credits: ${cr:,.2f}")
    print(f"  Net:     ${net:,.2f}")
    print()

c.close()
