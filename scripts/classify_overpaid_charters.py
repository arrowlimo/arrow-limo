#!/usr/bin/env python3
"""Classify remaining overpaid charters into remediation categories.

Categories:
  DUPLICATE_PAYMENT          - Overpayment caused by NULL-key or extra payments not in LMS
  ZERO_DUE_DUPLICATE         - Charter total_amount_due = 0 but paid_amount > 0 and LMS shows fewer payments
  CANCELLED_DEPOSIT          - Cancelled charter where paid_amount > total_amount_due (treat excess as credit)
  MULTI_CHARTER_PREPAY       - Large ETR payments intended for multiple future charters (detect large payments + other charters for client)
  MISALIGNED_TOTAL_DUE       - LMS Est_Charge differs from PG total_amount_due creating artificial excess
  NEED_MANUAL                - Edge cases not confidently auto-classifiable

Outputs:
  classification_overpaid_charters.csv

Dry-run only; does not modify data.
"""
import psycopg2, pyodbc, csv, math
from decimal import Decimal

PG = dict(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
LMS_PATH = r'L:\\limo\\backups\\lms.mdb'

LARGE_PAYMENT_THRESHOLD = Decimal('2500')  # heuristic for multi-charter prepay
MULTI_CHARTER_LOOKBACK_DAYS = 120

import datetime

def fetch_overpaid(pg_cur):
    pg_cur.execute("""
        SELECT c.reserve_number, c.charter_date, c.total_amount_due, c.paid_amount, c.balance, c.cancelled, cl.client_id, cl.client_name
        FROM charters c JOIN clients cl ON cl.client_id=c.client_id
        WHERE c.paid_amount > c.total_amount_due
        ORDER BY c.paid_amount - c.total_amount_due DESC
    """)
    return pg_cur.fetchall()

def lms_reserve(lms_cur, reserve_number):
    lms_cur.execute('SELECT Est_Charge, Deposit, Balance FROM Reserve WHERE Reserve_No=?', reserve_number)
    return lms_cur.fetchone()

def lms_payment_summary(lms_cur, reserve_number):
    # Access does not support COALESCE; handle None in Python
    lms_cur.execute('SELECT COUNT(*), SUM(Amount) FROM Payment WHERE Reserve_No=?', reserve_number)
    cnt, s = lms_cur.fetchone()
    if s is None:
        s = Decimal('0')
    return cnt, s

def pg_payments(pg_cur, reserve_number):
    pg_cur.execute("SELECT payment_id, amount, payment_key, payment_date, created_at FROM payments WHERE reserve_number=%s ORDER BY payment_date", (reserve_number,))
    return pg_cur.fetchall()

def other_charters(pg_cur, client_id, exclude_reserve):
    pg_cur.execute("""
        SELECT reserve_number, charter_date, total_amount_due, paid_amount, balance
        FROM charters WHERE client_id=%s AND reserve_number<>%s
        ORDER BY charter_date
    """, (client_id, exclude_reserve))
    return pg_cur.fetchall()


def classify_row(row, pg_cur, lms_cur):
    reserve_number, charter_date, due, paid, balance, cancelled, client_id, client_name = row
    pg_pay = pg_payments(pg_cur, reserve_number)
    lms_res = lms_reserve(lms_cur, reserve_number)
    lms_pay_count, lms_pay_sum = lms_payment_summary(lms_cur, reserve_number)
    pg_pay_count = len(pg_pay)
    pg_sum = sum(p[1] for p in pg_pay)

    excess = paid - due

    # DUPLICATE or ZERO_DUE_DUPLICATE detection
    null_key_payments = [p for p in pg_pay if p[2] is None]
    created_aug5 = [p for p in pg_pay if p[2] is None and p[4].date() == datetime.date(2025,8,5)]

    if due == 0 and paid > 0:
        # If LMS has fewer payments or no Est_Charge
        if lms_pay_count < pg_pay_count:
            return 'ZERO_DUE_DUPLICATE'
        # else treat as manual (could be placeholder charter)
        return 'NEED_MANUAL'

    # Cancelled deposits
    if cancelled and excess > 0:
        # If LMS deposit equals paid and Est_Charge small or zero -> deposit retention
        if lms_res and lms_res[0] in (Decimal('0.0000'), None):
            return 'CANCELLED_DEPOSIT'
        # Or if deposit recorded equals due but extra payments exist
        if lms_res and lms_res[1] == lms_res[0] and pg_sum > lms_res[0]:
            return 'CANCELLED_DEPOSIT'

    # Duplicate payments by count mismatch
    if lms_pay_count < pg_pay_count and (null_key_payments or created_aug5):
        return 'DUPLICATE_PAYMENT'

    # Misaligned total due
    if lms_res and lms_res[0] is not None and abs(lms_res[0] - Decimal(str(due))) > Decimal('0.01'):
        # LMS Est_Charge differs from PG total_amount_due
        if lms_res[0] < Decimal(str(due)) and paid - lms_res[0] <= LARGE_PAYMENT_THRESHOLD:
            return 'MISALIGNED_TOTAL_DUE'

    # Multi-charter prepayment detection: large individual ETR payments
    large_payments = [p for p in pg_pay if p[1] >= LARGE_PAYMENT_THRESHOLD and (p[2] or '').startswith('ETR:')]
    if large_payments:
        # Look for other charters needing money
        others = other_charters(pg_cur, client_id, reserve_number)
        unpaid_others = [o for o in others if o[4] > 0]  # balance >0
        if unpaid_others:
            return 'MULTI_CHARTER_PREPAY'

    return 'NEED_MANUAL'


def main():
    pg = psycopg2.connect(**PG)
    pg_cur = pg.cursor()
    lms = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
    lms_cur = lms.cursor()

    rows = fetch_overpaid(pg_cur)
    print(f"Classifying {len(rows)} overpaid charters...")

    out_rows = []
    counts = {}
    for r in rows:
        category = classify_row(r, pg_cur, lms_cur)
        counts[category] = counts.get(category, 0) + 1
        reserve_number, charter_date, due, paid, balance, cancelled, client_id, client_name = r
        out_rows.append([reserve_number, charter_date, float(due), float(paid), float(paid - due), cancelled, client_name, category])

    # Write CSV
    with open('classification_overpaid_charters.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['reserve_number','charter_date','total_amount_due','paid_amount','excess','cancelled','client_name','proposed_category'])
        w.writerows(out_rows)

    print('\nCategory counts:')
    for k,v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print('\nWritten classification_overpaid_charters.csv')

    lms_cur.close(); lms.close(); pg_cur.close(); pg.close()

if __name__ == '__main__':
    main()
