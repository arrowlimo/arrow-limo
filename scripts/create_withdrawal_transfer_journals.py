#!/usr/bin/env python3
"""
Create Bank → Petty Cash transfer journal entries for unlinked withdrawal transactions.

- Dry-run by default; requires --write and an override key to post.
- Uses table_protection to guard protected tables.
- Parameterized account codes to avoid hard-coding: --bank-account-code, --petty-cash-code
- Emits CSV preview of proposed entries.

Usage:
  python -X utf8 scripts/create_withdrawal_transfer_journals.py \
    --start 2025-10-01 --end 2025-10-31 \
    --bank-account-code 1010 --petty-cash-code 1000 \
    [--write] [--override-key ALLOW_WRITE_JOURNAL_YYYYMMDD]
"""

import os
import csv
import argparse
from datetime import datetime, date
import psycopg2
from psycopg2.extras import RealDictCursor

try:
    from table_protection import protect_deletion  # not used here but validates presence
except Exception:
    protect_deletion = None

WITHDRAWAL_PATTERNS = [
    'withdrawal', 'atm', 'cash withdrawal'
]


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )


def get_columns(cur, table):
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table,))
    return [r['column_name'] for r in cur.fetchall()]


def amount_expr(cols):
    if 'debit_amount' in cols and 'credit_amount' in cols:
        return '(COALESCE(credit_amount,0) - COALESCE(debit_amount,0))'
    elif 'amount' in cols:
        return 'amount'
    return '0'


def parse_date(s: str) -> date:
    return datetime.strptime(s, '%Y-%m-%d').date()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--start', required=True)
    p.add_argument('--end', required=True)
    p.add_argument('--bank-account-code', required=True)
    p.add_argument('--petty-cash-code', required=True)
    p.add_argument('--out', default='L:/limo/reports/withdrawal_transfer_candidates.csv')
    p.add_argument('--write', action='store_true')
    p.add_argument('--override-key', default=None)
    args = p.parse_args()

    d0 = parse_date(args.start)
    d1 = parse_date(args.end)

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    bt_cols = get_columns(cur, 'banking_transactions')
    amt = amount_expr(bt_cols)

    like = " OR ".join(["LOWER(description) LIKE %s" for _ in WITHDRAWAL_PATTERNS])
    params = [f"%{p.lower()}%" for p in WITHDRAWAL_PATTERNS]

    # Pull withdrawal candidates in date range, still unlinked to receipts
    cur.execute(
        f"""
        SELECT transaction_id, transaction_date, description, {amt} AS signed_amount
        FROM banking_transactions
        WHERE receipt_id IS NULL
          AND transaction_date BETWEEN %s AND %s
          AND ({amt}) < 0
          AND ({like})
        ORDER BY transaction_date, transaction_id
        """,
        [args.start, args.end, *params]
    )
    rows = cur.fetchall()

    if not rows:
        print('No withdrawal transfers found in selected date range. PASS (no-op)')
        return

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['transaction_id','transaction_date','description','amount','debit_account','credit_account'])
        for r in rows:
            w.writerow([
                r['transaction_id'], r['transaction_date'], r['description'], abs(float(r['signed_amount'] or 0)),
                args.petty_cash_code, args.bank_account_code
            ])
    print(f"CSV preview written: {args.out} ({len(rows)} rows)")

    if not args.write:
        print('Dry-run only. Use --write with override to post.')
        return

    # Verify protection module when writing
    if protect_deletion is None:
        print('Protection module not available; refusing to write.')
        return

    if not args.override_key or not args.override_key.startswith('ALLOW_WRITE_JOURNAL_'):
        print('Missing or invalid override key; refusing to write.')
        return

    # Determine journal schema and insert accordingly
    journal_cols = get_columns(cur, 'journal')
    lower_to_orig = {c.lower(): c for c in journal_cols}

    has_standard = all(k in lower_to_orig for k in ['transaction_date','account_code','description','debit_amount','credit_amount'])
    has_legacy = all(k in lower_to_orig for k in ['date','memo/description','account','debit','credit'])

    if not (has_standard or has_legacy):
        print('Journal schema not recognized (neither standard nor legacy columns found); refusing to write.')
        return

    # Journal ID handling (legacy schema often requires explicit primary key)
    has_jid = 'journal_id' in lower_to_orig
    next_id = None
    if has_jid:
        cur.execute('SELECT COALESCE(MAX(journal_id), 0) AS max_id FROM journal')
        row = cur.fetchone()
        max_id = list(row.values())[0] if row else 0
        next_id = (max_id or 0) + 1

    created = 0
    for r in rows:
        datev = r['transaction_date']
        amount = abs(float(r['signed_amount'] or 0))
        desc = f"Withdrawal transfer {r['transaction_id']}: {r['description']}"

        if has_standard:
            td = lower_to_orig['transaction_date']
            ac = lower_to_orig['account_code']
            ds = lower_to_orig['description']
            dr = lower_to_orig['debit_amount']
            cr = lower_to_orig['credit_amount']

            if has_jid:
                cur.execute(
                    f"""
                    INSERT INTO journal ("{td}", "{ac}", "{ds}", "{dr}", "{cr}", source_system, source_transaction_id, journal_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (datev, args.petty_cash_code, desc, amount, 0, 'bank_withdrawal_transfer', str(r['transaction_id']), next_id)
                )
                next_id += 1
                cur.execute(
                    f"""
                    INSERT INTO journal ("{td}", "{ac}", "{ds}", "{dr}", "{cr}", source_system, source_transaction_id, journal_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (datev, args.bank_account_code, desc, 0, amount, 'bank_withdrawal_transfer', str(r['transaction_id']), next_id)
                )
                next_id += 1
            else:
                cur.execute(
                    f"""
                    INSERT INTO journal ("{td}", "{ac}", "{ds}", "{dr}", "{cr}", source_system, source_transaction_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (datev, args.petty_cash_code, desc, amount, 0, 'bank_withdrawal_transfer', str(r['transaction_id']))
                )
                cur.execute(
                    f"""
                    INSERT INTO journal ("{td}", "{ac}", "{ds}", "{dr}", "{cr}", source_system, source_transaction_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (datev, args.bank_account_code, desc, 0, amount, 'bank_withdrawal_transfer', str(r['transaction_id']))
                )
        else:
            # Legacy QuickBooks-like schema: "Date", "Account", "Memo/Description", "Debit", "Credit"
            date_col = lower_to_orig['date']
            acct_col = lower_to_orig['account']
            memo_col = lower_to_orig['memo/description']
            debit_col = lower_to_orig['debit']
            credit_col = lower_to_orig['credit']

            if has_jid:
                cur.execute(
                    f"""
                    INSERT INTO journal ("{date_col}", "{acct_col}", "{memo_col}", "{debit_col}", "{credit_col}", journal_id)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    """,
                    (datev.strftime('%Y-%m-%d'), args.petty_cash_code, desc, amount, 0, next_id)
                )
                next_id += 1
                cur.execute(
                    f"""
                    INSERT INTO journal ("{date_col}", "{acct_col}", "{memo_col}", "{debit_col}", "{credit_col}", journal_id)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    """,
                    (datev.strftime('%Y-%m-%d'), args.bank_account_code, desc, 0, amount, next_id)
                )
                next_id += 1
            else:
                cur.execute(
                    f"""
                    INSERT INTO journal ("{date_col}", "{acct_col}", "{memo_col}", "{debit_col}", "{credit_col}")
                    VALUES (%s,%s,%s,%s,%s)
                    """,
                    (datev.strftime('%Y-%m-%d'), args.petty_cash_code, desc, amount, 0)
                )
                cur.execute(
                    f"""
                    INSERT INTO journal ("{date_col}", "{acct_col}", "{memo_col}", "{debit_col}", "{credit_col}")
                    VALUES (%s,%s,%s,%s,%s)
                    """,
                    (datev.strftime('%Y-%m-%d'), args.bank_account_code, desc, 0, amount)
                )
        created += 2

    conn.commit()
    print(f"Journal rows created: {created} (double-entry)")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
