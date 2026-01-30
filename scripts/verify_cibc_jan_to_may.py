#!/usr/bin/env python3
"""
CIBC Statement Verification: Jan–May by Month
=============================================
Summarize monthly transaction totals, opening/closing balances, and basic
anomalies for January through May (default year 2012) for one or more
CIBC accounts using the account_number_aliases infrastructure.

Usage examples:
  python -X utf8 scripts/verify_cibc_jan_to_may.py
  python -X utf8 scripts/verify_cibc_jan_to_may.py --year 2012 --statements 00339-7461615,3648117
  python -X utf8 scripts/verify_cibc_jan_to_may.py --canonical 0228362

Outputs a concise report suitable for cross-checking with screenshots.
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
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def find_account_by_statement_format(cur, statement_number):
    """Resolve a statement-format account to canonical using aliases table."""
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
    # If not found, assume caller might have passed canonical; verify existence
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM banking_transactions WHERE account_number = %s LIMIT 1
        )
        """,
        (statement_number,),
    )
    exists = cur.fetchone()[0]
    return (statement_number, '(assumed canonical - alias not found)') if exists else (None, None)


def month_bounds(year: int, month: int):
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def fetch_opening_closing(cur, canonical: str, month_start: date, month_end: date):
    """Get opening balance (closing of prior date) and month-end closing balance."""
    # Opening = last balance before month_start
    cur.execute(
        """
        SELECT balance
        FROM banking_transactions
        WHERE account_number = %s AND transaction_date < %s
        ORDER BY transaction_date DESC, transaction_id DESC
        LIMIT 1
        """,
        (canonical, month_start),
    )
    row = cur.fetchone()
    opening = row[0] if row and row[0] is not None else None

    # Closing = last balance on/before month_end
    cur.execute(
        """
        SELECT balance
        FROM banking_transactions
        WHERE account_number = %s AND transaction_date <= %s
        ORDER BY transaction_date DESC, transaction_id DESC
        LIMIT 1
        """,
        (canonical, month_end),
    )
    row = cur.fetchone()
    closing = row[0] if row and row[0] is not None else None

    return opening, closing


def fetch_month_totals(cur, canonical: str, month_start: date, month_end: date):
    cur.execute(
        """
        SELECT COUNT(*) AS cnt,
               SUM(debit_amount) AS debits,
               SUM(credit_amount) AS credits
        FROM banking_transactions
        WHERE account_number = %s
          AND transaction_date BETWEEN %s AND %s
        """,
        (canonical, month_start, month_end),
    )
    cnt, debits, credits = cur.fetchone()
    debits = debits or Decimal('0.00')
    credits = credits or Decimal('0.00')
    return cnt or 0, debits, credits, credits - debits


def fetch_quality_counts(cur, canonical: str, month_start: date, month_end: date):
    # Zero-amount rows
    cur.execute(
        """
        SELECT COUNT(*)
        FROM banking_transactions
        WHERE account_number = %s
          AND transaction_date BETWEEN %s AND %s
          AND COALESCE(debit_amount, 0) = 0
          AND COALESCE(credit_amount, 0) = 0
        """,
        (canonical, month_start, month_end),
    )
    zero_rows = cur.fetchone()[0]

    # Null/empty descriptions
    cur.execute(
        """
        SELECT COUNT(*)
        FROM banking_transactions
        WHERE account_number = %s
          AND transaction_date BETWEEN %s AND %s
          AND (description IS NULL OR TRIM(description) = '')
        """,
        (canonical, month_start, month_end),
    )
    null_desc = cur.fetchone()[0]

    # Duplicates by source_hash (if column exists)
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='banking_transactions' AND column_name='source_hash'
        )
        """
    )
    has_hash = cur.fetchone()[0]
    dup_count = 0
    if has_hash:
        cur.execute(
            """
            SELECT COALESCE(SUM(cnt - 1), 0) AS dupes
            FROM (
                SELECT source_hash, COUNT(*) AS cnt
                FROM banking_transactions
                WHERE account_number = %s
                  AND transaction_date BETWEEN %s AND %s
                  AND source_hash IS NOT NULL
                GROUP BY source_hash
                HAVING COUNT(*) > 1
            ) t
            """,
            (canonical, month_start, month_end),
        )
        dup_count = cur.fetchone()[0] or 0

    return zero_rows, null_desc, dup_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, default=2012, help='Year to verify (default 2012)')
    parser.add_argument('--months', type=str, default='1-5', help='Months to include, e.g., 1-5 or 1,2,3')
    parser.add_argument('--statements', type=str, default='00339-7461615,3648117', help='Comma-separated statement-format account numbers to resolve')
    parser.add_argument('--canonical', type=str, default=None, help='Comma-separated canonical account_number(s) to use directly')
    parser.add_argument('--export-csv', action='store_true', help='Export per-month transaction CSVs under reports/')
    args = parser.parse_args()

    # Parse months
    months = []
    if '-' in args.months:
        a, b = args.months.split('-', 1)
        months = list(range(int(a), int(b) + 1))
    else:
        months = [int(x) for x in args.months.split(',') if x.strip()]

    conn = get_db_connection()
    cur = conn.cursor()

    print('=' * 100)
    print(f'CIBC VERIFICATION SUMMARY - Jan–May {args.year}')
    print('=' * 100)

    # Build list of canonical accounts
    canonical_accounts = []
    if args.canonical:
        for c in args.canonical.split(','):
            canonical_accounts.append((c.strip(), '(provided canonical)'))
    else:
        for s in [x.strip() for x in args.statements.split(',') if x.strip()]:
            c, note = find_account_by_statement_format(cur, s)
            if c:
                canonical_accounts.append((c, note or ''))
            else:
                print(f"[WARN]  Could not resolve statement '{s}' to a canonical account; skipping.")

    if not canonical_accounts:
        print('No accounts to verify. Exiting.')
        return

    for canonical, note in canonical_accounts:
        print('\n' + '-' * 100)
        print(f"Account: {canonical}  ({note})")
        print('-' * 100)

        # Show basic account existence info
        cur.execute(
            """
            SELECT MIN(transaction_date), MAX(transaction_date), COUNT(*)
            FROM banking_transactions
            WHERE account_number = %s
            """,
            (canonical,),
        )
        min_d, max_d, total_cnt = cur.fetchone()
        print(f"Coverage: {min_d} → {max_d}  |  {total_cnt} total rows")

        for m in months:
            ms, me = month_bounds(args.year, m)
            cnt, deb, cred, net = fetch_month_totals(cur, canonical, ms, me)
            opening, closing = fetch_opening_closing(cur, canonical, ms, me)
            zero_rows, null_desc, dupes = fetch_quality_counts(cur, canonical, ms, me)

            # Compute expected closing from transactions if opening known
            expected_close = None
            discrepancy = None
            if opening is not None:
                expected_close = (opening or Decimal('0.00')) + (cred or Decimal('0.00')) - (deb or Decimal('0.00'))
                if closing is not None:
                    discrepancy = (closing or Decimal('0.00')) - expected_close

            print(f"\n  {ms.strftime('%b %Y')}: {cnt} txns")
            print(f"    Debits:  ${deb:,.2f}   Credits: ${cred:,.2f}   Net: ${net:,.2f}")
            if opening is not None and closing is not None:
                print(f"    Opening: ${opening:,.2f}   Closing: ${closing:,.2f}")
                if discrepancy is not None and abs(discrepancy) > Decimal('0.01'):
                    print(f"    [WARN]  Balance discrepancy: closing − (opening + credits − debits) = ${discrepancy:,.2f}")
                else:
                    print(f"    ✔ Balance equation holds within $0.01")
            else:
                missing = []
                if opening is None:
                    missing.append('opening')
                if closing is None:
                    missing.append('closing')
                print(f"    [WARN]  Missing {', '.join(missing)} balance snapshots; cannot cross-check balances.")

            if zero_rows or null_desc or dupes:
                print(f"    Data quality: zero-amount rows={zero_rows}, null/blank descriptions={null_desc}, duplicates={dupes}")

            # Optional: list top 5 largest debits and credits for manual spot-check
            cur.execute(
                """
                SELECT transaction_date, description, debit_amount
                FROM banking_transactions
                WHERE account_number = %s AND transaction_date BETWEEN %s AND %s AND debit_amount > 0
                ORDER BY debit_amount DESC, transaction_date
                LIMIT 3
                """,
                (canonical, ms, me),
            )
            top_debits = cur.fetchall()

            cur.execute(
                """
                SELECT transaction_date, description, credit_amount
                FROM banking_transactions
                WHERE account_number = %s AND transaction_date BETWEEN %s AND %s AND credit_amount > 0
                ORDER BY credit_amount DESC, transaction_date
                LIMIT 3
                """,
                (canonical, ms, me),
            )
            top_credits = cur.fetchall()

            if top_debits:
                print("    Largest debits:")
                for d, desc, amt in top_debits:
                    print(f"      {d}  -${amt:,.2f}  {desc[:60] if desc else ''}")
            if top_credits:
                print("    Largest credits:")
                for d, desc, amt in top_credits:
                    print(f"      {d}  +${amt:,.2f}  {desc[:60] if desc else ''}")

            # Optional CSV export of full month transactions for screenshot cross-check
            if args.export_csv:
                out_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
                out_dir = os.path.abspath(out_dir)
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, f"cibc_{canonical}_{ms.strftime('%Y_%m')}.csv")
                cur.execute(
                    """
                    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, balance
                    FROM banking_transactions
                    WHERE account_number = %s AND transaction_date BETWEEN %s AND %s
                    ORDER BY transaction_date, transaction_id
                    """,
                    (canonical, ms, me),
                )
                rows = cur.fetchall()
                with open(out_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['transaction_id', 'transaction_date', 'description', 'debit_amount', 'credit_amount', 'balance'])
                    for tid, td, desc, d_amt, c_amt, bal in rows:
                        writer.writerow([tid, td.isoformat(), (desc or '').strip(), f"{(d_amt or Decimal('0')):.2f}", f"{(c_amt or Decimal('0')):.2f}", f"{bal:.2f}" if bal is not None else ''])
                print(f"    📄 Exported: {out_path}")

    print('\n' + '=' * 100)
    print('Verification summary complete. Compare monthly lines to your screenshots.\n'
          'If any month shows a balance discrepancy or unexpected totals, tell me the page totals and we will drill in by day to find the offending rows.')

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
