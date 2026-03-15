#!/usr/bin/env python3
"""
Apply employee_id to driver_payroll using safe, deterministic joins.

Rules:
- Only UPDATE rows where driver_payroll.employee_id IS NULL
- Primary join: driver_payroll.driver_id = employees.employee_number
- Dry-run by default. Use --write to persist.
- Prints summary of affected rows and PASS/FAIL style result.

Usage:
  python -X utf8 scripts/apply_employee_id_to_driver_payroll.py [--write]
"""

import os
import argparse
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Apply updates instead of dry-run')
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Check columns exist defensively
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'driver_payroll'
    """)
    cols = {r['column_name'] for r in cur.fetchall()}
    required = {'driver_id', 'employee_id'}
    missing = required - cols
    if missing:
        print(f"FAIL: driver_payroll missing columns: {', '.join(sorted(missing))}")
        return

    cur.execute("""
        SELECT COUNT(*) AS c FROM driver_payroll WHERE employee_id IS NULL
    """)
    null_target = cur.fetchone()['c']
    print(f"Rows with NULL employee_id: {null_target}")

    # Preview join impact
    cur.execute("""
        SELECT COUNT(*) AS c
        FROM driver_payroll dp
        JOIN employees e ON CAST(e.employee_number AS TEXT) = CAST(dp.driver_id AS TEXT)
        WHERE dp.employee_id IS NULL
    """)
    joinable = cur.fetchone()['c']
    print(f"Rows joinable by driver_id=employee_number: {joinable}")

    if joinable == 0:
        print("No rows to update via primary rule. PASS (no-op)")
        return

    if not args.write:
        print("Dry-run only. Use --write to apply.")
        return

    # Apply update
    cur.execute("""
        UPDATE driver_payroll dp
        SET employee_id = e.employee_id
        FROM employees e
        WHERE dp.employee_id IS NULL
          AND CAST(e.employee_number AS TEXT) = CAST(dp.driver_id AS TEXT)
    """)
    updated = cur.rowcount
    conn.commit()

    print(f"Updated rows: {updated}")
    status = 'PASS' if updated == joinable else 'PARTIAL'
    print(f"Result: {status}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
