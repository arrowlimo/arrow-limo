#!/usr/bin/env python3
"""
Validate user-supplied screenshot page/month totals against banking_transactions.

Two modes:
1) Generate a monthly template for a given year and list of accounts:
   python -X utf8 scripts/validate_screenshot_totals.py --year 2012 --statements 00339-7461615,3648117 --generate-template
   -> writes reports/screenshot_totals_2012_template.csv with rows for Jan–Dec per account

2) Validate an input CSV with expected totals (user fills from screenshots):
   python -X utf8 scripts/validate_screenshot_totals.py --input reports/screenshot_totals_2012_template.csv --validate --exclude-zero

CSV columns:
  account_statement_format, start_date, end_date, expected_debits, expected_credits, expected_opening, expected_closing
Additional computed output columns on validation:
  db_debits, db_credits, db_opening, db_closing, debits_diff, credits_diff, opening_diff, closing_diff, status

Notes:
- account_statement_format is resolved to canonical via account_number_aliases
- --exclude-zero skips rows where both debit and credit are zero
- Opening/closing balances based on last balance before start_date, and last balance on/before end_date
"""
import argparse
import csv
import os
from datetime import date, timedelta
from decimal import Decimal

import psycopg2


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    )


def find_account_by_statement_format(cur, statement_number):
    cur.execute(
        """
        SELECT canonical_account_number, notes
        FROM account_number_aliases
        WHERE statement_format = %s
        """,
        (statement_number,),
    )
    row = cur.fetchone()
    if row:
        return row[0], row[1]
    # fallback: maybe canonical
    cur.execute("SELECT EXISTS (SELECT 1 FROM banking_transactions WHERE account_number = %s LIMIT 1)", (statement_number,))
    if cur.fetchone()[0]:
        return statement_number, '(assumed canonical)'
    return None, None


def month_bounds(year: int, month: int):
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def fetch_open_close(cur, canonical: str, start_d: date, end_d: date):
    cur.execute(
        """
        SELECT balance
        FROM banking_transactions
        WHERE account_number = %s AND transaction_date < %s
        ORDER BY transaction_date DESC, transaction_id DESC
        LIMIT 1
        """,
        (canonical, start_d),
    )
    row = cur.fetchone(); opening = row[0] if row and row[0] is not None else None

    cur.execute(
        """
        SELECT balance
        FROM banking_transactions
        WHERE account_number = %s AND transaction_date <= %s
        ORDER BY transaction_date DESC, transaction_id DESC
        LIMIT 1
        """,
        (canonical, end_d),
    )
    row = cur.fetchone(); closing = row[0] if row and row[0] is not None else None
    return opening, closing


def fetch_sums(cur, canonical: str, start_d: date, end_d: date, exclude_zero: bool):
    if exclude_zero:
        cur.execute(
            """
            SELECT SUM(debit_amount), SUM(credit_amount)
            FROM banking_transactions
            WHERE account_number = %s AND transaction_date BETWEEN %s AND %s
              AND NOT (COALESCE(debit_amount,0)=0 AND COALESCE(credit_amount,0)=0)
            """,
            (canonical, start_d, end_d),
        )
    else:
        cur.execute(
            """
            SELECT SUM(debit_amount), SUM(credit_amount)
            FROM banking_transactions
            WHERE account_number = %s AND transaction_date BETWEEN %s AND %s
            """,
            (canonical, start_d, end_d),
        )
    deb, cred = cur.fetchone()
    return (deb or Decimal('0')), (cred or Decimal('0'))


def generate_template(cur, year: int, statements: list, out_path: str):
    rows = []
    for stmt in statements:
        canonical, _ = find_account_by_statement_format(cur, stmt)
        if not canonical:
            continue
        for m in range(1, 13):
            ms, me = month_bounds(year, m)
            rows.append([stmt, ms.isoformat(), me.isoformat(), '', '', '', ''])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['account_statement_format','start_date','end_date','expected_debits','expected_credits','expected_opening','expected_closing'])
        w.writerows(rows)
    print(f'📄 Template generated: {out_path}')


def validate_input(cur, in_csv: str, out_csv: str, exclude_zero: bool):
    with open(in_csv, 'r', encoding='utf-8') as f, open(out_csv, 'w', newline='', encoding='utf-8') as g:
        r = csv.DictReader(f)
        fieldnames = r.fieldnames + ['db_debits','db_credits','db_opening','db_closing','debits_diff','credits_diff','opening_diff','closing_diff','status','canonical']
        w = csv.DictWriter(g, fieldnames=fieldnames)
        w.writeheader()
        for row in r:
            stmt = (row.get('account_statement_format') or '').strip()
            start_s = (row.get('start_date') or '').strip()
            end_s = (row.get('end_date') or '').strip()
            if not stmt or not start_s or not end_s:
                continue
            start_d = date.fromisoformat(start_s)
            end_d = date.fromisoformat(end_s)
            canonical, _ = find_account_by_statement_format(cur, stmt)
            if not canonical:
                row.update({
                    'db_debits':'','db_credits':'','db_opening':'','db_closing':'',
                    'debits_diff':'','credits_diff':'','opening_diff':'','closing_diff':'',
                    'status':'NO_ACCOUNT','canonical':''
                })
                w.writerow(row); continue
            db_deb, db_cred = fetch_sums(cur, canonical, start_d, end_d, exclude_zero)
            db_open, db_close = fetch_open_close(cur, canonical, start_d, end_d)
            exp_deb = Decimal((row.get('expected_debits') or '0').replace(',','')) if row.get('expected_debits') else None
            exp_cred = Decimal((row.get('expected_credits') or '0').replace(',','')) if row.get('expected_credits') else None
            exp_open = Decimal((row.get('expected_opening') or '0').replace(',','')) if row.get('expected_opening') else None
            exp_close = Decimal((row.get('expected_closing') or '0').replace(',','')) if row.get('expected_closing') else None

            deb_diff = (exp_deb - db_deb) if exp_deb is not None else None
            cred_diff = (exp_cred - db_cred) if exp_cred is not None else None
            open_diff = (exp_open - db_open) if (exp_open is not None and db_open is not None) else None
            close_diff = (exp_close - db_close) if (exp_close is not None and db_close is not None) else None

            status = 'OK'
            for diff in [deb_diff, cred_diff, open_diff, close_diff]:
                if diff is not None and abs(diff) > Decimal('0.01'):
                    status = 'MISMATCH'; break

            row.update({
                'db_debits': f'{db_deb:.2f}',
                'db_credits': f'{db_cred:.2f}',
                'db_opening': f'{db_open:.2f}' if db_open is not None else '',
                'db_closing': f'{db_close:.2f}' if db_close is not None else '',
                'debits_diff': f'{deb_diff:.2f}' if deb_diff is not None else '',
                'credits_diff': f'{cred_diff:.2f}' if cred_diff is not None else '',
                'opening_diff': f'{open_diff:.2f}' if open_diff is not None else '',
                'closing_diff': f'{close_diff:.2f}' if close_diff is not None else '',
                'status': status,
                'canonical': canonical,
            })
            w.writerow(row)
    print(f'[OK] Validation written: {out_csv}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--year', type=int, default=2012)
    ap.add_argument('--statements', type=str, default='00339-7461615,3648117')
    ap.add_argument('--generate-template', action='store_true')
    ap.add_argument('--input', type=str, default=None)
    ap.add_argument('--validate', action='store_true')
    ap.add_argument('--exclude-zero', action='store_true', help='Exclude zero-amount rows from sums')
    args = ap.parse_args()

    conn = get_db_connection(); cur = conn.cursor()

    reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports'))
    os.makedirs(reports_dir, exist_ok=True)

    if args.generate_template:
        stmts = [x.strip() for x in args.statements.split(',') if x.strip()]
        out_path = os.path.join(reports_dir, f'screenshot_totals_{args.year}_template.csv')
        generate_template(cur, args.year, stmts, out_path)

    if args.validate:
        if not args.input:
            print('[FAIL] --input CSV required for --validate')
        else:
            base, _ = os.path.splitext(os.path.basename(args.input))
            out_csv = os.path.join(reports_dir, f'{base}_validated.csv')
            validate_input(cur, args.input, out_csv, args.exclude_zero)

    cur.close(); conn.close()


if __name__ == '__main__':
    main()
