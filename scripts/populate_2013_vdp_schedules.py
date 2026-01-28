#!/usr/bin/env python3
import os, csv, psycopg2
from datetime import date

BASE = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'reports', 'VDP_2013'))
SCHED_DIR = os.path.join(BASE, 'schedules')

START = '2013-01-01'
END = '2014-01-01'

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REMOVED***')
    )

def table_has_column(cur, table, column):
    cur.execute("SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s", (table, column))
    return cur.fetchone() is not None

def sum_payroll_withholds(cur):
    # Determine date column: prefer pay_date, else imported_at
    has_pay_date = table_has_column(cur, 'driver_payroll', 'pay_date')
    date_col = 'pay_date' if has_pay_date else 'imported_at'
    base = f"SELECT ROUND(COALESCE(SUM(cpp),0)::numeric,2), ROUND(COALESCE(SUM(ei),0)::numeric,2), ROUND(COALESCE(SUM(tax),0)::numeric,2) FROM driver_payroll WHERE {date_col} >= %s AND {date_col} < %s"
    if table_has_column(cur, 'driver_payroll', 'payroll_class'):
        base += " AND (payroll_class <> 'ADJUSTMENT' OR payroll_class IS NULL)"
    cur.execute(base, (START, END))
    row = cur.fetchone()
    return float(row[0] or 0), float(row[1] or 0), float(row[2] or 0)

def sum_banking_remittances(cur):
    # Sum debits that look like CRA remittances
    patterns = [
        '%receiver general%', '%canada revenue agency%', '%cra%', '%receiver gen%', '%revenue canada%'
    ]
    has_vendor = table_has_column(cur, 'banking_transactions', 'vendor_extracted')
    conds = ["(COALESCE(description,'') ILIKE ANY (%s))"]
    params = [patterns]
    if has_vendor:
        conds.append("(COALESCE(vendor_extracted,'') ILIKE ANY (%s))")
        params.append(patterns)
    where_like = " OR ".join(conds)
    sql = f"""
    SELECT COUNT(*), ROUND(COALESCE(SUM(debit_amount),0)::numeric,2)
    FROM banking_transactions
    WHERE transaction_date >= %s AND transaction_date < %s
      AND ({where_like})
    """
    cur.execute(sql, (START, END, *params))
    row = cur.fetchone()
    return int(row[0] or 0), float(row[1] or 0)

def write_payroll_schedule(cpp_amt, ei_amt, tax_amt, rem_count, rem_amt):
    path = os.path.join(SCHED_DIR, 'payroll_pd7a_support.csv')
    rows = [
        ['CPP Withheld', f"{cpp_amt:.2f}", 'driver_payroll', f'{START}..{END}'],
        ['EI Withheld', f"{ei_amt:.2f}", 'driver_payroll', f'{START}..{END}'],
        ['Income Tax Withheld', f"{tax_amt:.2f}", 'driver_payroll', f'{START}..{END}'],
        ['Remitted to CRA (banking debits)', f"{rem_amt:.2f}", 'banking_transactions', f'matches={rem_count}']
    ]
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['component','amount','source','notes'])
        w.writerows(rows)

def append_gst_schedule_remittance(rem_amt):
    path = os.path.join(SCHED_DIR, 'gst34_support.csv')
    # Append if file exists, else create minimal
    rows = []
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            rows = list(csv.reader(f))
    header = ['component','amount','source','notes']
    if not rows:
        rows = [header]
    rows.append(['Banking Remittances Found (2013)', f"{rem_amt:.2f}", 'banking_transactions', f'{START}..{END}'])
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow(r)


def main():
    os.makedirs(SCHED_DIR, exist_ok=True)
    conn = get_conn(); cur = conn.cursor()
    cpp_amt, ei_amt, tax_amt = sum_payroll_withholds(cur)
    rem_count, rem_amt = sum_banking_remittances(cur)
    write_payroll_schedule(cpp_amt, ei_amt, tax_amt, rem_count, rem_amt)
    append_gst_schedule_remittance(rem_amt)
    cur.close(); conn.close()
    print(f"PD7A schedule updated. CRA remittances matches={rem_count}, amount={rem_amt:.2f}")

if __name__ == '__main__':
    main()
