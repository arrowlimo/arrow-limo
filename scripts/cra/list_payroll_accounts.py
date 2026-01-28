#!/usr/bin/env python
import psycopg2

c = psycopg2.connect('dbname=almsdata user=postgres password=***REMOVED***')
r = c.cursor()
r.execute("SELECT DISTINCT account FROM general_ledger WHERE account IS NOT NULL ORDER BY account")
accts = [x[0] for x in r.fetchall()]
print(f'Total accounts: {len(accts)}\n')

print("Payroll-related accounts:")
for a in accts:
    if any(kw in a.lower() for kw in ['cpp', 'ei ', ' ei', 'tax', 'deduct', 'withhold', 'payroll', 'remit']):
        print(f"  {a}")

c.close()
