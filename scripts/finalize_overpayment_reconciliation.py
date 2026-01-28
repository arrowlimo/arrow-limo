#!/usr/bin/env python3
"""Produce final overpayment reconciliation report."""
import psycopg2
from decimal import Decimal

PG = dict(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')

pg = psycopg2.connect(**PG); cur = pg.cursor()

cur.execute('SELECT COUNT(*) FROM charters WHERE paid_amount > total_amount_due')
overpaid_count = cur.fetchone()[0]
cur.execute('SELECT COALESCE(SUM(paid_amount - total_amount_due),0) FROM charters WHERE paid_amount > total_amount_due')
overpaid_sum = cur.fetchone()[0] or 0

cur.execute('SELECT COUNT(*), COALESCE(SUM(credit_amount),0), COALESCE(SUM(remaining_balance),0) FROM charter_credit_ledger')
ledger_stats = cur.fetchone()

cur.execute("""
  SELECT credit_reason, COUNT(*), SUM(credit_amount), SUM(remaining_balance)
  FROM charter_credit_ledger
  GROUP BY credit_reason ORDER BY SUM(credit_amount) DESC
""")
reason_rows = cur.fetchall()

print('FINAL OVERPAYMENT RECONCILIATION REPORT')
print('======================================')
print(f'Charters still overpaid: {overpaid_count} (sum excess {float(overpaid_sum):.2f})')
print(f'Total credit ledger entries: {ledger_stats[0]}')
print(f'Total credit amount: {float(ledger_stats[1]):.2f}')
print(f'Total remaining balance (available credits): {float(ledger_stats[2]):.2f}')
print('\nBy Credit Reason:')
for r, cnt, amt, rem in reason_rows:
    print(f'  {r:<20} entries={cnt:<5} amount={float(amt):>10.2f} remaining={float(rem):>10.2f}')

cur.close(); pg.close()
