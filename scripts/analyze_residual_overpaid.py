#!/usr/bin/env python3
"""Analyze residual overpaid charters after main remediation.
Outputs residual_overpaid_analysis.csv with columns:
 reserve_number, client_name, pg_due, pg_paid, excess, charge_sum, lms_est_charge, lms_deposit, lms_balance,
 pg_payment_count, lms_payment_count, category, recommended_action
Categories:
  CHARGES_MISMATCH - charter_charges sum > total_amount_due (adjust due)
  LMS_DUE_HIGHER   - LMS Est_Charge > PG due (adjust due)
  STILL_DUPLICATES - PG payment count > LMS payment count
  SMALL_ROUNDING   - excess <= 5.00 may be rounding
  REVIEW_MANUAL    - none of above
"""
import psycopg2, pyodbc, csv
from decimal import Decimal

PG = dict(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
LMS_PATH = r'L:\\limo\\backups\\lms.mdb'

pg = psycopg2.connect(**PG); cur = pg.cursor()
lms = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'); lcur = lms.cursor()

cur.execute("""
 SELECT c.reserve_number, c.total_amount_due, c.paid_amount, c.balance, cl.client_name, c.charter_id
 FROM charters c JOIN clients cl ON cl.client_id=c.client_id
 WHERE c.paid_amount > c.total_amount_due
 ORDER BY c.paid_amount - c.total_amount_due DESC
""")
rows = cur.fetchall()
print(f"Residual overpaid count: {len(rows)}")

out = []
for reserve, due, paid, bal, client, charter_id in rows:
    excess = paid - due
    # charter charges sum
    cur.execute('SELECT COALESCE(SUM(amount),0) FROM charter_charges WHERE reserve_number=%s', (reserve,))
    charge_sum = cur.fetchone()[0] or 0
    # LMS reserve row
    lcur.execute('SELECT Est_Charge, Deposit, Balance FROM Reserve WHERE Reserve_No=?', reserve)
    lms_row = lcur.fetchone()
    est_charge = lms_row[0] if lms_row else None
    lms_deposit = lms_row[1] if lms_row else None
    lms_balance = lms_row[2] if lms_row else None
    # Payment counts
    cur.execute('SELECT COUNT(*) FROM payments WHERE reserve_number=%s', (reserve,))
    pg_payment_count = cur.fetchone()[0]
    lcur.execute('SELECT COUNT(*) FROM Payment WHERE Reserve_No=?', reserve)
    lms_payment_count = lcur.fetchone()[0]

    category = 'REVIEW_MANUAL'
    action = 'review'
    # Determine mismatches
    # Ensure Decimal numeric comparisons
    if isinstance(charge_sum, float):
        charge_sum = Decimal(str(charge_sum))
    if isinstance(due, float):
        due_dec = Decimal(str(due))
    else:
        due_dec = due
    if charge_sum and charge_sum > due_dec + Decimal('0.01'):
        category = 'CHARGES_MISMATCH'
        action = 'increase_due_to_charge_sum'
    elif est_charge and est_charge > due_dec + Decimal('0.01'):
        category = 'LMS_DUE_HIGHER'
        action = 'increase_due_to_LMS'
    elif pg_payment_count > lms_payment_count:
        category = 'STILL_DUPLICATES'
        action = 'delete_extra_payments'
    elif excess <= 5:
        category = 'SMALL_ROUNDING'
        action = 'credit_or_adjust_due'

    out.append([reserve, client, float(due), float(paid), float(excess), float(charge_sum), float(est_charge or 0), float(lms_deposit or 0), float(lms_balance or 0), pg_payment_count, lms_payment_count, category, action])

with open('residual_overpaid_analysis.csv','w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['reserve_number','client_name','pg_due','pg_paid','excess','charge_sum','lms_est_charge','lms_deposit','lms_balance','pg_payment_count','lms_payment_count','category','recommended_action'])
    w.writerows(out)

print('Written residual_overpaid_analysis.csv')

lcur.close(); lms.close(); cur.close(); pg.close()
