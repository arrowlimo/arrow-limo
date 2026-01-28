#!/usr/bin/env python3
"""
Report linkage coverage for staging_driver_pay using v_staging_driver_pay_with_employee.

Outputs:
- Total rows, rows with names, rows linked (resolved_employee_id not null)
- Coverage by year/month of txn_date if present, else by source file id if available
- Top 15 unmatched driver_name samples for triage
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


def has_view(cur, name: str) -> bool:
    cur.execute("SELECT EXISTS (SELECT FROM information_schema.views WHERE table_name = %s) AS ok", (name,))
    return cur.fetchone()['ok']


def column_exists(cur, table_or_view: str, col: str) -> bool:
    cur.execute("""
        SELECT EXISTS (
          SELECT FROM information_schema.columns
          WHERE table_name = %s AND column_name = %s
        ) AS ok
    """, (table_or_view, col))
    return cur.fetchone()['ok']


def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if not has_view(cur, 'v_staging_driver_pay_with_employee'):
        print("View v_staging_driver_pay_with_employee not found. Run create_staging_driver_pay_view.py first.")
        return

    # Basic totals
    cur.execute("SELECT COUNT(*) AS c FROM v_staging_driver_pay_with_employee")
    total = cur.fetchone()['c']

    cur.execute("""
        SELECT COUNT(*) AS c
        FROM v_staging_driver_pay_with_employee
        WHERE TRIM(COALESCE(driver_name,'')) <> ''
    """)
    with_name = cur.fetchone()['c']

    cur.execute("""
        SELECT COUNT(*) AS c
        FROM v_staging_driver_pay_with_employee
        WHERE resolved_employee_id IS NOT NULL
    """)
    linked = cur.fetchone()['c']

    print("="*80)
    print("STAGING DRIVER PAY LINKAGE COVERAGE")
    print("="*80)
    print(f"Total rows:              {total}")
    print(f"Rows with driver_name:   {with_name}")
    print(f"Rows linked (resolved):  {linked}")

    # Coverage by year/month if txn_date exists
    group_expr = None
    if column_exists(cur, 'v_staging_driver_pay_with_employee', 'txn_date'):
        group_expr = "EXTRACT(YEAR FROM txn_date)::int AS year, EXTRACT(MONTH FROM txn_date)::int AS month"
        from_expr = "v_staging_driver_pay_with_employee"
    else:
        # fallback: count by source_row_id modulo ranges (just a placeholder grouping)
        group_expr = "0 AS year, 0 AS month"
        from_expr = "v_staging_driver_pay_with_employee"

    cur.execute(
        f"""
        SELECT {group_expr},
               COUNT(*) AS rows,
               SUM(CASE WHEN resolved_employee_id IS NOT NULL THEN 1 ELSE 0 END) AS linked_rows
        FROM {from_expr}
        GROUP BY 1,2
        ORDER BY 1,2
        """
    )
    buckets = cur.fetchall()

    print("\nCoverage by year/month:")
    print(f"{'Year':<6} {'Month':<6} {'Rows':>8} {'Linked':>8} {'Coverage%':>10}")
    print('-'*48)
    for b in buckets:
        y = b['year'] if b['year'] is not None else 0
        m = b['month'] if b['month'] is not None else 0
        rows = b['rows']
        linked_rows = b['linked_rows'] or 0
        cov = (linked_rows / rows * 100.0) if rows else 0.0
        print(f"{y:<6} {m:<6} {rows:>8} {linked_rows:>8} {cov:>9.1f}%")

    # Show top unmatched names
    cur.execute(
        """
        SELECT driver_name, COUNT(*) AS rows
        FROM v_staging_driver_pay_with_employee
        WHERE resolved_employee_id IS NULL
          AND TRIM(COALESCE(driver_name,'')) <> ''
        GROUP BY driver_name
        ORDER BY rows DESC
        LIMIT 15
        """
    )
    top_unmatched = cur.fetchall()

    if top_unmatched:
        print("\nTop unmatched driver_name values:")
        for r in top_unmatched:
            print(f"  {r['driver_name']}: {r['rows']}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
