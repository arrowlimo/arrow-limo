#!/usr/bin/env python3
"""
Enhanced deposits ↔ payments reconciliation with tolerance and grouping.

- Dry-run by default; writes suggested links to link table banking_payment_links when --write is used.
- Matching methods:
  1) exact date + amount
  2) date + amount within tolerance
  3) grouped deposits per date ≈ sum of payments for that date (within tolerance)
- Emits CSV preview of suggestions and a summary.

Usage:
  python -X utf8 scripts/reconcile_deposits_to_payments_enhanced.py \
    --start 2025-10-01 --end 2025-10-31 --tolerance 0.01 [--write]
"""

import os
import csv
import argparse
from decimal import Decimal
from datetime import datetime, date
import psycopg2
from psycopg2.extras import RealDictCursor

DEPOSIT_PATTERNS = [
    'deposit', 'cheque', 'check', 'ck ', 'cash deposit', 'branch deposit', 'visa deposit', 'debit deposit', 'abm deposit'
]


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )


def parse_date(s: str) -> date:
    return datetime.strptime(s, '%Y-%m-%d').date()


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


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--start', required=True)
    p.add_argument('--end', required=True)
    p.add_argument('--tolerance', type=float, default=0.01)
    p.add_argument('--out', default='L:/limo/reports/deposit_payment_suggestions.csv')
    p.add_argument('--write', action='store_true')
    args = p.parse_args()

    d0 = parse_date(args.start)
    d1 = parse_date(args.end)
    tol = Decimal(str(args.tolerance))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    bt_cols = get_columns(cur, 'banking_transactions')
    pm_cols = get_columns(cur, 'payments')

    amt = amount_expr(bt_cols)
    p_amount_col = 'amount' if 'amount' in pm_cols else ('payment_amount' if 'payment_amount' in pm_cols else None)
    p_date_col = 'payment_date' if 'payment_date' in pm_cols else ('created_at' if 'created_at' in pm_cols else None)

    if p_amount_col is None or p_date_col is None:
        print('Payments table missing amount/date columns; aborting.')
        return

    like = " OR ".join(["LOWER(description) LIKE %s" for _ in DEPOSIT_PATTERNS])
    params = [f"%{p.lower()}%" for p in DEPOSIT_PATTERNS]

    # Gather deposits in range
    cur.execute(
        f"""
        SELECT transaction_id, transaction_date, description, {amt} AS amount
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
          AND ({amt}) > 0
          AND ({like})
        ORDER BY transaction_date, transaction_id
        """,
        [args.start, args.end, *params]
    )
    deposits = cur.fetchall()

    if not deposits:
        print('No deposits in range. PASS (no-op)')
        return

    # Fetch payments grouped by date
    cur.execute(
        f"""
        SELECT {p_date_col}::date AS pdate, {p_amount_col} AS amount, payment_id
        FROM payments
        WHERE {p_amount_col} IS NOT NULL
          AND {p_date_col}::date BETWEEN %s AND %s
        """,
        [args.start, args.end]
    )
    payments = cur.fetchall()

    # Build date-indexed structures
    from collections import defaultdict
    pay_by_date = defaultdict(list)
    sum_by_date = defaultdict(Decimal)

    for pmt in payments:
        amt = Decimal(str(pmt['amount'] or 0))
        pdate = pmt['pdate']
        pay_by_date[pdate].append(pmt)
        sum_by_date[pdate] += amt

    suggestions = []

    # Create link table if writing
    if args.write:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS banking_payment_links (
                id SERIAL PRIMARY KEY,
                banking_transaction_id INTEGER NOT NULL,
                payment_id INTEGER NOT NULL,
                method TEXT,
                confidence NUMERIC(5,4),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (banking_transaction_id, payment_id)
            )
            """
        )

    # Matching
    for dep in deposits:
        d_amt = Decimal(str(dep['amount'] or 0))
        d_date = dep['transaction_date']
        d_id = dep['transaction_id']

        candidates = pay_by_date.get(d_date, [])
        exact = [p for p in candidates if Decimal(str(p['amount'] or 0)) == d_amt]
        if exact:
            for pmt in exact:
                suggestions.append((d_id, pmt['payment_id'], 'date+amount', Decimal('0.999')))
            continue

        # Tolerance match (single payment)
        near = [p for p in candidates if abs(Decimal(str(p['amount'] or 0)) - d_amt) <= tol]
        if len(near) == 1:
            suggestions.append((d_id, near[0]['payment_id'], 'date+amount≈tol', Decimal('0.95')))
            continue

        # Grouped payments sum per date
        total_for_day = sum_by_date.get(d_date, Decimal('0'))
        if abs(total_for_day - d_amt) <= tol and len(candidates) > 1:
            # Link deposit to each payment that composes the total (lower confidence)
            for pmt in candidates:
                suggestions.append((d_id, pmt['payment_id'], 'grouped-sum', Decimal('0.80')))
            continue

        # No suggestion

    # Output CSV
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['banking_transaction_id','payment_id','method','confidence'])
        for s in suggestions:
            w.writerow([s[0], s[1], s[2], f"{s[3]:.3f}"])
    print(f"Suggestions written: {args.out} ({len(suggestions)} rows)")

    if not args.write:
        print('Dry-run only. Use --write to store links in banking_payment_links.')
        cur.close(); conn.close(); return

    # Write links (idempotent unique constraint)
    created = 0
    for d_id, p_id, method, conf in suggestions:
        cur.execute(
            """
            INSERT INTO banking_payment_links (banking_transaction_id, payment_id, method, confidence)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (banking_transaction_id, payment_id) DO UPDATE
            SET method = EXCLUDED.method, confidence = EXCLUDED.confidence
            """,
            (d_id, p_id, method, float(conf))
        )
        created += 1

    conn.commit()
    print(f"Links upserted: {created}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
