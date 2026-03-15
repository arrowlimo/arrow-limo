#!/usr/bin/env python3
"""
Banking coverage and reconciliation prep summary.

Outputs:
- banking_transactions coverage by year and month (counts and totals)
- detection of which column carries the signed amount (debit vs credit)
- email_financial_events linkage coverage (linked vs unlinked)
- quick PASS/FAIL thresholds for known benchmark years when available
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )


def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print('='*80)
    print('BANKING COVERAGE SUMMARY')
    print('='*80)

    # Confirm banking_transactions schema and which columns exist
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'banking_transactions'
        ORDER BY ordinal_position
        """
    )
    cols = {row['column_name'] for row in cur.fetchall()}
    has_debit = 'debit_amount' in cols
    has_credit = 'credit_amount' in cols
    has_amount = 'amount' in cols

    print('\nColumns detected in banking_transactions:')
    print('  - ' + ', '.join(sorted(cols)))

    # Build signed amount expression (best-effort)
    amount_expr = None
    if has_debit and has_credit:
        # Convention: debit = money leaving; credit = money coming in
        amount_expr = '(COALESCE(credit_amount,0) - COALESCE(debit_amount,0))'
    elif has_amount:
        amount_expr = 'amount'
    else:
        amount_expr = '0'

    # Coverage by year/month
    cur.execute(
        f"""
        SELECT EXTRACT(YEAR FROM transaction_date)::int as year,
               EXTRACT(MONTH FROM transaction_date)::int as month,
               COUNT(*) as rows,
               SUM(CASE WHEN {amount_expr} >= 0 THEN {amount_expr} ELSE 0 END) as total_in,
               SUM(CASE WHEN {amount_expr} < 0 THEN {amount_expr} ELSE 0 END) as total_out
        FROM banking_transactions
        GROUP BY 1,2
        ORDER BY 1,2
        """
    )
    ym = cur.fetchall()

    by_year = {}
    for r in ym:
        y = r['year']
        by_year.setdefault(y, {'rows': 0, 'in': 0.0, 'out': 0.0})
        by_year[y]['rows'] += r['rows']
        by_year[y]['in'] += float(r['total_in'] or 0)
        by_year[y]['out'] += float(r['total_out'] or 0)

    print('\nCoverage by year:')
    print(f"{'Year':<6} {'Rows':>8} {'Total In':>16} {'Total Out':>16}")
    print('-'*52)
    for y in sorted(by_year.keys()):
        yr = by_year[y]
        print(f"{y:<6} {yr['rows']:>8} {yr['in']:>16,.2f} {yr['out']:>16,.2f}")

    # Email events reconciliation coverage
    # Check if email_financial_events exists
    cur.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables WHERE table_name = 'email_financial_events'
        ) as exists
        """
    )
    efe_exists = cur.fetchone()['exists']

    if efe_exists:
        cur.execute("SELECT COUNT(*) AS c FROM email_financial_events")
        efe_total = cur.fetchone()['c']
        cur.execute("SELECT COUNT(*) AS c FROM email_financial_events WHERE banking_transaction_id IS NOT NULL")
        efe_linked = cur.fetchone()['c']
        print('\nEmail financial events:')
        print(f"  Total:   {efe_total}")
        print(f"  Linked:  {efe_linked}")
        print(f"  Unlinked:{efe_total - efe_linked}")
    else:
        print('\nEmail financial events table not found (skipping).')

    # Simple PASS/FAIL benchmarks (if present)
    # Example: ensure 2017 has roughly expected row count (if that year exists)
    if 2017 in by_year:
        expected_min = 1750  # heuristic threshold
        status = 'PASS' if by_year[2017]['rows'] >= expected_min else 'FAIL'
        print(f"\nBenchmark 2017 rows >= {expected_min}: {by_year[2017]['rows']} -> {status}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
