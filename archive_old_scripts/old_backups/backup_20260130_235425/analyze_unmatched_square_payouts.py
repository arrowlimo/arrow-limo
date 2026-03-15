#!/usr/bin/env python3
"""
Analyze UNMATCHED Square payouts from the reconciliation CSV and look for likely
banking/receipt candidates within a wider window. Produces a diagnostics CSV.
"""
import os, csv
from datetime import datetime, timedelta
import psycopg2

DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = int(os.environ.get('DB_PORT', '5432'))

RECON_CSV = r"l:/limo/reports/square_banking_reconciliation.csv"
OUT_CSV = r"l:/limo/reports/square_unmatched_diagnostics.csv"
DATE_WINDOW_DAYS = int(os.environ.get('SQUARE_DIAG_DATE_WINDOW_DAYS', '7'))
TOL = float(os.environ.get('SQUARE_DIAG_TOLERANCE', '0.02'))

conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
cur = conn.cursor()

unmatched = []
with open(RECON_CSV, newline='', encoding='utf-8') as f:
    rdr = csv.DictReader(f)
    for row in rdr:
        if (row.get('status') or '').upper() == 'UNMATCHED':
            unmatched.append(row)

rows = []
for r in unmatched:
    poid = r['payout_id']
    pd = r['payout_date']
    amt = float(r['payout_amount']) if r.get('payout_amount') else 0.0
    d = datetime.fromisoformat(pd).date()
    d0 = d - timedelta(days=DATE_WINDOW_DAYS)
    d1 = d + timedelta(days=DATE_WINDOW_DAYS)

    # Exact/near matches in banking_transactions
    cur.execute("""
        SELECT transaction_id, transaction_date, account_number, credit_amount, description,
               ABS(credit_amount - %s) AS diff
          FROM banking_transactions
         WHERE transaction_date BETWEEN %s AND %s
           AND credit_amount IS NOT NULL AND credit_amount > 0
         ORDER BY diff ASC, transaction_date ASC
         LIMIT 5
    """, (amt, d0, d1))
    bt = cur.fetchall()
    bt_exact = [b for b in bt if abs(float(b[3]) - amt) <= TOL]

    # Exact/near matches in receipts_finance_view (inflows)
    cur.execute("""
        SELECT v.receipt_id, v.receipt_date, v.vendor_name, v.inflow_amount,
               ABS(v.inflow_amount - %s) AS diff
          FROM receipts_finance_view v
         WHERE v.receipt_date BETWEEN %s AND %s AND v.inflow_amount > 0
         ORDER BY diff ASC, v.receipt_date ASC
         LIMIT 5
    """, (amt, d0, d1))
    rv = cur.fetchall()
    rv_exact = [x for x in rv if abs(float(x[3]) - amt) <= TOL]

    rows.append({
        'payout_id': poid,
        'payout_date': pd,
        'payout_amount': amt,
        'bt_exact_count': len(bt_exact),
        'bt_top1_date': bt[0][1] if bt else '',
        'bt_top1_amount': bt[0][3] if bt else '',
        'bt_top1_desc': bt[0][4][:80] if bt else '',
        'rv_exact_count': len(rv_exact),
        'rv_top1_date': rv[0][1] if rv else '',
        'rv_top1_amount': rv[0][3] if rv else '',
        'rv_top1_vendor': rv[0][2][:80] if rv else '',
        'diagnosis': (
            'Likely missing bank import' if len(bt_exact)==0 and len(rv_exact)==0 else (
                'Use banking_transactions exact' if len(bt_exact)>0 else 'Use receipts inflow exact'
            )
        )
    })

os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
with open(OUT_CSV, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=[
        'payout_id','payout_date','payout_amount',
        'bt_exact_count','bt_top1_date','bt_top1_amount','bt_top1_desc',
        'rv_exact_count','rv_top1_date','rv_top1_amount','rv_top1_vendor',
        'diagnosis'
    ])
    w.writeheader()
    w.writerows(rows)

print(f"Diagnostics written: {OUT_CSV} ({len(rows)} unmatched analyzed)")
