#!/usr/bin/env python3
"""Mark an employee inactive by employee_number.

Usage:
  python -X utf8 scripts/mark_employee_inactive.py --code Dr01
"""
import argparse
import os
import psycopg2

PG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    dbname=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--code", required=True, help="Employee number code, e.g., Dr01")
    args = p.parse_args()
    code = args.code

    with psycopg2.connect(**PG) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT employee_id, status FROM employees WHERE employee_number=%s LIMIT 1", (code,))
            row = cur.fetchone()
            if not row:
                print(f"No employee found for {code}")
                return
            emp_id, status = row
            cur.execute("UPDATE employees SET status='inactive' WHERE employee_number=%s", (code,))
            conn.commit()
            print(f"Marked employee_number={code} (employee_id={emp_id}) inactive (was '{status}')")


if __name__ == "__main__":
    main()
