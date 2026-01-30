#!/usr/bin/env python3
"""
Snapshot Jan–May monthly summary for CIBC accounts and save to CSV + JSON.
Locks current verification progress so we don't lose state.

Outputs:
  - reports/cibc_jan_to_may_2012_summary.csv
  - reports/cibc_jan_to_may_2012_summary.json

Columns per row:
  account_number, month, start_date, end_date, count, debits, credits, net,
  opening, closing, balance_discrepancy, zero_amount_rows, null_descriptions, duplicates
"""
import csv
import json
import os
from datetime import date, timedelta
from decimal import Decimal
import psycopg2


def get_db_connection():
    import os
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def month_bounds(year: int, month: int):
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def fetch_open_close(cur, acct: str, start_d: date, end_d: date):
    cur.execute(
        """
        SELECT balance FROM banking_transactions
        WHERE account_number=%s AND transaction_date < %s
        ORDER BY transaction_date DESC, transaction_id DESC LIMIT 1
        """,
        (acct, start_d),
    )
    row = cur.fetchone(); opening = row[0] if row and row[0] is not None else None
    cur.execute(
        """
        SELECT balance FROM banking_transactions
        WHERE account_number=%s AND transaction_date <= %s
        ORDER BY transaction_date DESC, transaction_id DESC LIMIT 1
        """,
        (acct, end_d),
    )
    row = cur.fetchone(); closing = row[0] if row and row[0] is not None else None
    return opening, closing


def fetch_month(cur, acct: str, start_d: date, end_d: date):
    cur.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(debit_amount),0), COALESCE(SUM(credit_amount),0)
        FROM banking_transactions
        WHERE account_number=%s AND transaction_date BETWEEN %s AND %s
        """,
        (acct, start_d, end_d),
    )
    cnt, deb, cred = cur.fetchone()
    # Zero amount rows
    cur.execute(
        """
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number=%s AND transaction_date BETWEEN %s AND %s
          AND COALESCE(debit_amount,0)=0 AND COALESCE(credit_amount,0)=0
        """,
        (acct, start_d, end_d),
    )
    zero_rows = cur.fetchone()[0]
    # Null/blank description
    cur.execute(
        """
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number=%s AND transaction_date BETWEEN %s AND %s
          AND (description IS NULL OR TRIM(description)='')
        """,
        (acct, start_d, end_d),
    )
    null_desc = cur.fetchone()[0]
    # Duplicates by source_hash
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='banking_transactions' AND column_name='source_hash'
        )
        """
    )
    has_hash = cur.fetchone()[0]
    dupes = 0
    if has_hash:
        cur.execute(
            """
            SELECT COALESCE(SUM(cnt-1),0) FROM (
              SELECT source_hash, COUNT(*) AS cnt
              FROM banking_transactions
              WHERE account_number=%s AND transaction_date BETWEEN %s AND %s AND source_hash IS NOT NULL
              GROUP BY source_hash HAVING COUNT(*)>1
            ) t
            """,
            (acct, start_d, end_d),
        )
        dupes = cur.fetchone()[0] or 0

    return cnt or 0, Decimal(deb or 0), Decimal(cred or 0), zero_rows, null_desc, dupes


def main():
    YEAR = 2012
    ACCOUNTS = ['0228362', '3648117']

    conn = get_db_connection()
    cur = conn.cursor()

    rows = []
    for acct in ACCOUNTS:
        for m in range(1,6):
            ms, me = month_bounds(YEAR, m)
            cnt, deb, cred, zero_rows, null_desc, dupes = fetch_month(cur, acct, ms, me)
            opening, closing = fetch_open_close(cur, acct, ms, me)
            net = cred - deb
            discrepancy = None
            if opening is not None and closing is not None:
                expected_close = (opening or Decimal('0')) + (cred or Decimal('0')) - (deb or Decimal('0'))
                discrepancy = (closing or Decimal('0')) - expected_close
            rows.append({
                'account_number': acct,
                'month': ms.strftime('%Y-%m'),
                'start_date': ms.isoformat(),
                'end_date': me.isoformat(),
                'count': int(cnt),
                'debits': float(deb),
                'credits': float(cred),
                'net': float(net),
                'opening': float(opening) if opening is not None else None,
                'closing': float(closing) if closing is not None else None,
                'balance_discrepancy': float(discrepancy) if discrepancy is not None else None,
                'zero_amount_rows': int(zero_rows),
                'null_descriptions': int(null_desc),
                'duplicates': int(dupes),
            })

    reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports'))
    os.makedirs(reports_dir, exist_ok=True)
    csv_path = os.path.join(reports_dir, 'cibc_jan_to_may_2012_summary.csv')
    json_path = os.path.join(reports_dir, 'cibc_jan_to_may_2012_summary.json')

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['account_number','month','start_date','end_date','count','debits','credits','net','opening','closing','balance_discrepancy','zero_amount_rows','null_descriptions','duplicates'])
        for r in rows:
            w.writerow([r['account_number'], r['month'], r['start_date'], r['end_date'], r['count'], f"{r['debits']:.2f}", f"{r['credits']:.2f}", f"{r['net']:.2f}", '' if r['opening'] is None else f"{r['opening']:.2f}", '' if r['closing'] is None else f"{r['closing']:.2f}", '' if r['balance_discrepancy'] is None else f"{r['balance_discrepancy']:.2f}", r['zero_amount_rows'], r['null_descriptions'], r['duplicates']])

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, indent=2)

    print(f'📄 Snapshot written:\n  {csv_path}\n  {json_path}')

    cur.close(); conn.close()


if __name__ == '__main__':
    main()
