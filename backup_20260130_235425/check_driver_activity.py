#!/usr/bin/env python3
"""Check whether a driver code (e.g., Dr01) has real activity or pay.

Outputs:
- reports/driver_activity_summary_<CODE>_<DATE>.csv
- reports/driver_activity_details_<CODE>_<DATE>.csv

Metrics:
- Employees match: employee_id, full_name
- Charters linked by number (charters.driver) or ID (assigned_driver_id / secondary_driver_id)
- Charges count from charter_charges (if exists)
- Payroll presence from employee_monthly_compensation / employee_annual_compensation (if exists)
- Receipts linked to employee_id (if exists)
"""
import argparse
import csv
import datetime
import os
import psycopg2
import psycopg2.extras as extras

PG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    dbname=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
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


def get_columns(cur, table_name: str) -> set:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table_name,),
    )
    return {r[0] for r in cur.fetchall()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", default="Dr01", help="Driver code (e.g., Dr01)")
    args = parser.parse_args()
    code = args.code

    os.makedirs(REPORT_DIR, exist_ok=True)

    with psycopg2.connect(**PG) as conn:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            emp_cols = get_columns(cur, "employees")
            ch_cols = get_columns(cur, "charters")

            # Employee match
            emp_id = None
            emp_name = None
            if "employee_number" in emp_cols:
                cur.execute(
                    """
                    SELECT employee_id, full_name
                    FROM employees
                    WHERE employee_number = %s
                    LIMIT 1
                    """,
                    (code,),
                )
                row = cur.fetchone()
                if row:
                    emp_id, emp_name = row[0], row[1]

            # Charters activity
            charter_count_by_number = 0
            charter_count_by_id = 0
            charter_status_breakdown = {}
            details_rows = []

            # By number string
            cur.execute(
                """
                SELECT charter_id, status, booking_status
                FROM charters
                WHERE driver = %s
                """,
                (code,),
            )
            for cid, status, booking_status in cur.fetchall():
                charter_count_by_number += 1
                key = (status or "").strip().lower() or "unknown"
                charter_status_breakdown[key] = charter_status_breakdown.get(key, 0) + 1
                details_rows.append([cid, "by-number", status, booking_status])

            # By assigned/secondary id
            if emp_id is not None:
                if "assigned_driver_id" in ch_cols:
                    cur.execute(
                        """
                        SELECT charter_id, status, booking_status
                        FROM charters
                        WHERE assigned_driver_id = %s
                        """,
                        (emp_id,),
                    )
                    for cid, status, booking_status in cur.fetchall():
                        charter_count_by_id += 1
                        key = (status or "").strip().lower() or "unknown"
                        charter_status_breakdown[key] = charter_status_breakdown.get(key, 0) + 1
                        details_rows.append([cid, "by-id-assigned", status, booking_status])
                if "secondary_driver_id" in ch_cols:
                    cur.execute(
                        """
                        SELECT charter_id, status, booking_status
                        FROM charters
                        WHERE secondary_driver_id = %s
                        """,
                        (emp_id,),
                    )
                    for cid, status, booking_status in cur.fetchall():
                        charter_count_by_id += 1
                        key = (status or "").strip().lower() or "unknown"
                        charter_status_breakdown[key] = charter_status_breakdown.get(key, 0) + 1
                        details_rows.append([cid, "by-id-secondary", status, booking_status])

            # Charges
            charges_count = 0
            charges_sum = 0.0
            if table_exists(cur, "charter_charges"):
                if charter_count_by_number > 0:
                    cur.execute(
                        """
                        SELECT COUNT(*), COALESCE(SUM(amount),0)
                        FROM charter_charges cc
                        WHERE cc.charter_id IN (
                            SELECT charter_id FROM charters WHERE driver = %s
                        )
                        """,
                        (code,),
                    )
                    res = cur.fetchone()
                    charges_count += (res[0] or 0)
                    charges_sum += float(res[1] or 0.0)
                if emp_id is not None and charter_count_by_id > 0:
                    cur.execute(
                        """
                        SELECT COUNT(*), COALESCE(SUM(amount),0)
                        FROM charter_charges cc
                        WHERE cc.charter_id IN (
                            SELECT charter_id FROM charters WHERE assigned_driver_id = %s OR secondary_driver_id = %s
                        )
                        """,
                        (emp_id, emp_id),
                    )
                    res = cur.fetchone()
                    charges_count += (res[0] or 0)
                    charges_sum += float(res[1] or 0.0)

            # Payroll
            payroll_records = 0
            gross_pay_sum = 0.0
            monthly_exists = table_exists(cur, "employee_monthly_compensation")
            annual_exists = table_exists(cur, "employee_annual_compensation")
            if emp_id is not None and monthly_exists:
                cur.execute(
                    "SELECT COUNT(*), COALESCE(SUM(gross_pay),0) FROM employee_monthly_compensation WHERE employee_id=%s",
                    (emp_id,),
                )
                r = cur.fetchone(); payroll_records += (r[0] or 0); gross_pay_sum += float(r[1] or 0.0)
            if emp_id is not None and annual_exists:
                cur.execute(
                    "SELECT COUNT(*), COALESCE(SUM(gross_pay),0) FROM employee_annual_compensation WHERE employee_id=%s",
                    (emp_id,),
                )
                r = cur.fetchone(); payroll_records += (r[0] or 0); gross_pay_sum += float(r[1] or 0.0)

            # Receipts linked to employee
            receipts_exists = table_exists(cur, "receipts")
            receipt_count = 0
            receipt_sum = 0.0
            if emp_id is not None and receipts_exists and ("employee_id" in get_columns(cur, "receipts")):
                cur.execute(
                    "SELECT COUNT(*), COALESCE(SUM(amount),0) FROM receipts WHERE employee_id=%s",
                    (emp_id,),
                )
                r = cur.fetchone(); receipt_count = (r[0] or 0); receipt_sum = float(r[1] or 0.0)

            # Summary
            summary_rows = [
                ["code", code],
                ["employee_id", emp_id if emp_id is not None else "(not found)"],
                ["employee_name", emp_name or ""],
                ["charters_by_number", charter_count_by_number],
                ["charters_by_id", charter_count_by_id],
                ["charges_count", charges_count],
                ["charges_sum", f"{charges_sum:.2f}"],
                ["payroll_records", payroll_records],
                ["gross_pay_sum", f"{gross_pay_sum:.2f}"],
                ["receipt_count", receipt_count],
                ["receipt_sum", f"{receipt_sum:.2f}"],
            ]
            write_csv(
                os.path.join(REPORT_DIR, f"driver_activity_summary_{code}_{DATE_SUFFIX}.csv"),
                ["metric", "value"],
                summary_rows,
            )
            write_csv(
                os.path.join(REPORT_DIR, f"driver_activity_details_{code}_{DATE_SUFFIX}.csv"),
                ["charter_id", "linked_by", "status", "booking_status"],
                details_rows,
            )

            print("=== Driver Activity Audit ===")
            print(f"Code: {code}; Employee: {emp_id} - {emp_name}")
            print(f"Charters by number: {charter_count_by_number}; by id: {charter_count_by_id}")
            print(f"Charges: count={charges_count}, sum={charges_sum:.2f}")
            print(f"Payroll: records={payroll_records}, gross_sum={gross_pay_sum:.2f}")
            print(f"Receipts: count={receipt_count}, sum={receipt_sum:.2f}")
            print("Outputs written under reports/ with date suffix.")


if __name__ == "__main__":
    main()
