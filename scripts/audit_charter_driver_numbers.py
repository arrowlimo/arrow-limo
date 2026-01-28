#!/usr/bin/env python3
"""Audit that all driver numbers come from employees table.

Checks:
- charters.driver (string) values exist in employees.employee_number
- charters.assigned_driver_id references valid employees.employee_id

Outputs:
- reports/charter_driver_numbers_audit_<DATE>.csv
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


def get_existing_columns(cur, table_name: str) -> set:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table_name,),
    )
    return {r[0] for r in cur.fetchall()}


def write_csv(path: str, headers, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    with psycopg2.connect(**PG) as conn:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            emp_cols = get_existing_columns(cur, "employees")
            ch_cols = get_existing_columns(cur, "charters")

            # Employees baseline sets
            cur.execute("SELECT COUNT(*) FROM employees")
            total_employees = cur.fetchone()[0] or 0

            emp_numbers = set()
            if "employee_number" in emp_cols:
                cur.execute(
                    """
                    SELECT DISTINCT employee_number
                    FROM employees
                    WHERE employee_number IS NOT NULL AND TRIM(employee_number) <> ''
                    """
                )
                emp_numbers = {r[0] for r in cur.fetchall()}

            emp_ids = set()
            id_col = "employee_id" if "employee_id" in emp_cols else ("id" if "id" in emp_cols else None)
            if id_col:
                cur.execute(f"SELECT DISTINCT {id_col} FROM employees")
                emp_ids = {r[0] for r in cur.fetchall()}

            # Audit charters.driver (string number) mismatches
            missing_driver_numbers = []
            if "driver" in ch_cols and emp_numbers:
                cur.execute(
                    """
                    SELECT charter_id, driver
                    FROM charters
                    WHERE driver IS NOT NULL AND TRIM(driver) <> ''
                    """
                )
                for cid, drv in cur.fetchall():
                    if drv not in emp_numbers:
                        missing_driver_numbers.append([cid, drv])

            # Audit assigned_driver_id FK-like integrity
            missing_assigned_ids = []
            if "assigned_driver_id" in ch_cols and emp_ids:
                cur.execute(
                    """
                    SELECT charter_id, assigned_driver_id
                    FROM charters
                    WHERE assigned_driver_id IS NOT NULL
                    """
                )
                for cid, did in cur.fetchall():
                    if did not in emp_ids:
                        missing_assigned_ids.append([cid, did])

            # Write report
            rows = [
                ["date", DATE_SUFFIX],
                ["total_employees", total_employees],
                ["employee_numbers", len(emp_numbers)],
                ["employee_ids", len(emp_ids)],
                ["charters_with_missing_driver_number", len(missing_driver_numbers)],
                ["charters_with_missing_assigned_driver_id", len(missing_assigned_ids)],
            ]
            write_csv(
                os.path.join(
                    REPORT_DIR,
                    f"charter_driver_numbers_audit_{DATE_SUFFIX}.csv",
                ),
                ["metric", "value"],
                rows,
            )

            # Detail files
            if missing_driver_numbers:
                write_csv(
                    os.path.join(
                        REPORT_DIR,
                        f"charter_missing_driver_numbers_{DATE_SUFFIX}.csv",
                    ),
                    ["charter_id", "driver"],
                    missing_driver_numbers,
                )
            if missing_assigned_ids:
                write_csv(
                    os.path.join(
                        REPORT_DIR,
                        f"charter_missing_assigned_driver_ids_{DATE_SUFFIX}.csv",
                    ),
                    ["charter_id", "assigned_driver_id"],
                    missing_assigned_ids,
                )

            print("=== Charter Driver Numbers Audit ===")
            print(f"Employees: {total_employees}")
            print(f"Employee numbers available: {len(emp_numbers)}; employee IDs: {len(emp_ids)}")
            print(f"Charters driver-number mismatches: {len(missing_driver_numbers)}")
            print(f"Charters assigned-driver-id mismatches: {len(missing_assigned_ids)}")
            print("Outputs written under reports/ with date suffix.")


if __name__ == "__main__":
    main()
