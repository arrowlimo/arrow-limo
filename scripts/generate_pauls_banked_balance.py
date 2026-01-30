#!/usr/bin/env python3
"""
Compute Paul's banked balances by year (2014+):
- Sum gross_pay from driver_payroll for employees with names containing 'Paul'
- Heuristic: sum probable payouts from banking transactions whose descriptions contain the Paul's last names
- Output by year: payroll_gross, probable_payouts, estimated_banked_balance = payroll_gross - probable_payouts

Writes exports/driver_audit/paul_banked_balance_by_year.csv
"""

import psycopg2
import csv
from pathlib import Path
from collections import defaultdict

DB = dict(dbname='almsdata', user='postgres', password='***REDACTED***', host='localhost')
OUT = Path(__file__).parent.parent / 'exports' / 'driver_audit' / 'paul_banked_balance_by_year.csv'


def connect():
    return psycopg2.connect(**DB)


def main():
    conn = connect(); cur = conn.cursor()

    # Paul employees
    cur.execute("""
        SELECT employee_id, employee_number, COALESCE(full_name, first_name || ' ' || last_name) AS name
        FROM employees
        WHERE LOWER(COALESCE(full_name, first_name || ' ' || last_name)) LIKE '%paul%'
    """)
    pauls = cur.fetchall()

    lastnames = set()
    for emp_id, emp_no, name in pauls:
        if name:
            parts = name.strip().split()
            if len(parts) >= 2:
                lastnames.add(parts[-1].lower())

    # Payroll by year for Pauls
    cur.execute("""
        SELECT EXTRACT(YEAR FROM pay_date)::INT AS yr, SUM(gross_pay) as total
        FROM driver_payroll
        WHERE pay_date >= DATE '2014-01-01'
          AND (
            employee_id IN (SELECT employee_id FROM employees WHERE LOWER(COALESCE(full_name, first_name || ' ' || last_name)) LIKE '%paul%')
            OR driver_id IN (SELECT employee_number FROM employees WHERE LOWER(COALESCE(full_name, first_name || ' ' || last_name)) LIKE '%paul%')
          )
        GROUP BY yr
        ORDER BY yr
    """)
    payroll_by_year = {row[0]: float(row[1] or 0) for row in cur.fetchall()}

    # Probable payouts by year via banking description match
    payouts_by_year = defaultdict(float)
    for ln in lastnames:
        cur.execute("""
            SELECT EXTRACT(YEAR FROM transaction_date)::INT AS yr, SUM(debit_amount)
            FROM banking_transactions
            WHERE transaction_date >= DATE '2014-01-01'
              AND debit_amount > 0
              AND LOWER(description) LIKE %s
            GROUP BY yr
        """, (f"%{ln}%",))
        for yr, total in cur.fetchall():
            payouts_by_year[int(yr)] += float(total or 0)

    # Combine
    years = sorted(set(list(payroll_by_year.keys()) + list(payouts_by_year.keys())))

    rows = []
    for yr in years:
        payroll = payroll_by_year.get(yr, 0.0)
        payout = payouts_by_year.get(yr, 0.0)
        banked = payroll - payout
        rows.append({'year': yr, 'payroll_gross': payroll, 'probable_payouts': payout, 'estimated_banked_balance': banked})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['year','payroll_gross','probable_payouts','estimated_banked_balance'])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"Paul banked balance by year written to: {OUT}")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
