#!/usr/bin/env python3
"""Audit owner (Paul Richard) pay/tax status.

Confirms:
- Identify employee record for Paul Richard (prefer code Dr100).
- Last payroll month/year (employee_monthly_compensation).
- Last annual compensation year (employee_annual_compensation).
- Any payroll entries after 2013.
- Any T4 records (t4 tables) and last T4 year.

Outputs:
- reports/owner_pay_status_summary_2025-12-25.csv
- reports/owner_pay_status_details_post_2013_2025-12-25.csv
"""
import csv
import datetime
import os
import psycopg2
import psycopg2.extras as extras

PG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    dbname=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
REPORT_DIR = os.path.join(ROOT_DIR, "reports")
DATE_SUFFIX = datetime.date.today().isoformat()


def write_csv(path: str, headers, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def table_exists(cur, table_name: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema='public' AND table_name=%s
        )
        """,
        (table_name,),
    )
    return bool(cur.fetchone()[0])


def find_paul_employee(cur):
    # Prefer code Dr100; fallback by name contains 'Richard' and 'Paul'
    cur.execute("SELECT employee_id, employee_number, full_name FROM employees WHERE employee_number='Dr100' LIMIT 1")
    row = cur.fetchone()
    if row:
        return row[0], row[1], row[2]
    cur.execute("SELECT employee_id, employee_number, full_name FROM employees WHERE LOWER(full_name) LIKE '%richard%' AND LOWER(full_name) LIKE '%paul%' LIMIT 1")
    row = cur.fetchone()
    if row:
        return row[0], row[1], row[2]
    return None, None, None


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    with psycopg2.connect(**PG) as conn:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            emp_id, emp_num, emp_name = find_paul_employee(cur)
            if not emp_id:
                print("Paul Richard not found in employees.")
                write_csv(
                    os.path.join(REPORT_DIR, f"owner_pay_status_summary_{DATE_SUFFIX}.csv"),
                    ["metric", "value"],
                    [["found", "no"]],
                )
                return

            # Monthly compensation
            last_monthly = None
            post_2013_monthly_count = 0
            post_2013_monthly_sum = 0.0
            if table_exists(cur, "employee_monthly_compensation"):
                cur.execute(
                    """
                    SELECT MAX(make_date(year, month, 1)) AS last_date
                    FROM employee_monthly_compensation
                    WHERE employee_id=%s AND COALESCE(gross_pay,0) > 0
                    """,
                    (emp_id,),
                )
                last_monthly = cur.fetchone()[0]
                cur.execute(
                    """
                    SELECT COUNT(*), COALESCE(SUM(gross_pay),0)
                    FROM employee_monthly_compensation
                    WHERE employee_id=%s AND year > 2013 AND COALESCE(gross_pay,0) > 0
                    """,
                    (emp_id,),
                )
                r = cur.fetchone(); post_2013_monthly_count = r[0] or 0; post_2013_monthly_sum = float(r[1] or 0.0)

            # Annual compensation
            last_annual_year = None
            post_2013_annual_count = 0
            post_2013_annual_sum = 0.0
            if table_exists(cur, "employee_annual_compensation"):
                cur.execute(
                    """
                    SELECT MAX(year)
                    FROM employee_annual_compensation
                    WHERE employee_id=%s AND COALESCE(gross_pay,0) > 0
                    """,
                    (emp_id,),
                )
                last_annual_year = cur.fetchone()[0]
                cur.execute(
                    """
                    SELECT COUNT(*), COALESCE(SUM(gross_pay),0)
                    FROM employee_annual_compensation
                    WHERE employee_id=%s AND year > 2013 AND COALESCE(gross_pay,0) > 0
                    """,
                    (emp_id,),
                )
                r = cur.fetchone(); post_2013_annual_count = r[0] or 0; post_2013_annual_sum = float(r[1] or 0.0)

            # T4-like tables: try to locate any table with 't4' in name
            last_t4_year = None
            cur.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema='public' AND table_name LIKE 't4%'
                """
            )
            t4_tables = [r[0] for r in cur.fetchall()]
            for tname in t4_tables:
                # Try common columns year/employee_id
                cur.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema='public' AND table_name=%s
                    """,
                    (tname,),
                )
                cols = {r[0] for r in cur.fetchall()}
                if 'year' in cols and ('employee_id' in cols or 'emp_id' in cols):
                    id_col = 'employee_id' if 'employee_id' in cols else 'emp_id'
                    cur.execute(
                        f"SELECT MAX(year) FROM {tname} WHERE {id_col}=%s",
                        (emp_id,),
                    )
                    y = cur.fetchone()[0]
                    if y:
                        last_t4_year = max(last_t4_year or y, y)

            # Details of any post-2013 monthly entries
            details_rows = []
            if post_2013_monthly_count > 0:
                cur.execute(
                    """
                    SELECT year, month, gross_pay
                    FROM employee_monthly_compensation
                    WHERE employee_id=%s AND year > 2013 AND COALESCE(gross_pay,0) > 0
                    ORDER BY year, month
                    """,
                    (emp_id,),
                )
                for y, m, gp in cur.fetchall():
                    details_rows.append([y, m, float(gp or 0.0)])

            # Summary output
            summary = [
                ["employee_id", emp_id],
                ["employee_number", emp_num or ""],
                ["employee_name", emp_name or ""],
                ["last_monthly_pay_date", last_monthly.isoformat() if last_monthly else "(none)"],
                ["last_annual_pay_year", last_annual_year if last_annual_year else "(none)"],
                ["post_2013_monthly_count", post_2013_monthly_count],
                ["post_2013_monthly_sum", f"{post_2013_monthly_sum:.2f}"],
                ["post_2013_annual_count", post_2013_annual_count],
                ["post_2013_annual_sum", f"{post_2013_annual_sum:.2f}"],
                ["last_t4_year", last_t4_year if last_t4_year is not None else "(none)"],
            ]
            write_csv(
                os.path.join(REPORT_DIR, f"owner_pay_status_summary_{DATE_SUFFIX}.csv"),
                ["metric", "value"],
                summary,
            )
            write_csv(
                os.path.join(REPORT_DIR, f"owner_pay_status_details_post_2013_{DATE_SUFFIX}.csv"),
                ["year", "month", "gross_pay"],
                details_rows,
            )

            print("=== Owner Pay Status Audit ===")
            print(f"Employee: {emp_id} - {emp_num} - {emp_name}")
            print(f"Last monthly pay date: {summary[3][1]}")
            print(f"Last annual pay year: {summary[4][1]}")
            print(f"Post-2013 monthly records: {post_2013_monthly_count} (${post_2013_monthly_sum:.2f})")
            print(f"Post-2013 annual records: {post_2013_annual_count} (${post_2013_annual_sum:.2f})")
            print(f"Last T4 year: {summary[9][1]}")
            print("Outputs under reports/ with date suffix.")


if __name__ == "__main__":
    main()
