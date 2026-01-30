#!/usr/bin/env python3
"""Confirm that charters with missing/non-employee driver numbers have zero charges or are cancelled.

Logic:
- Identify charters where `charters.driver` is non-empty and NOT in `employees.employee_number`.
- For each, check:
  - Charges count from `charter_charges` (if table exists).
  - Cancellation status via `charters.status` or `charters.booking_status` (case-insensitive, values: cancelled, canceled, void, deleted).

Outputs:
- reports/missing_driver_numbers_safety_summary_<DATE>.csv
- reports/missing_driver_numbers_safety_details_<DATE>.csv
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
    os.makedirs(REPORT_DIR, exist_ok=True)
    with psycopg2.connect(**PG) as conn:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            emp_cols = get_columns(cur, "employees")
            ch_cols = get_columns(cur, "charters")

            # Build employees numbers set
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

            # Fetch candidate charters
            select_fields = ["charter_id", "driver"]
            if "status" in ch_cols:
                select_fields.append("status")
            if "booking_status" in ch_cols:
                select_fields.append("booking_status")
            cur.execute(f"SELECT {', '.join(select_fields)} FROM charters WHERE driver IS NOT NULL AND TRIM(driver) <> ''")

            candidates = []
            for row in cur.fetchall():
                rec = {select_fields[i].split(' AS ')[-1]: row[i] for i in range(len(select_fields))}
                driver = rec["driver"]
                if driver not in emp_numbers:
                    candidates.append(rec)

            # Charges table exists?
            charges_exists = table_exists(cur, "charter_charges")

            safe_count = 0
            exception_count = 0
            details_rows = []
            for rec in candidates:
                cid = rec.get("charter_id")
                driver = rec.get("driver")
                status = (rec.get("status") or "").strip().lower()
                booking_status = (rec.get("booking_status") or "").strip().lower()
                charges_count = 0
                if charges_exists:
                    cur.execute("SELECT COUNT(*) FROM charter_charges WHERE charter_id=%s", (cid,))
                    charges_count = cur.fetchone()[0] or 0
                is_cancelled = status in {"cancelled", "canceled", "void", "deleted"} or booking_status in {"cancelled", "canceled", "void", "deleted"}
                safe = (charges_count == 0) or is_cancelled
                if safe:
                    safe_count += 1
                else:
                    exception_count += 1
                details_rows.append([
                    cid,
                    driver,
                    status,
                    booking_status,
                    charges_count,
                    "SAFE" if safe else "EXCEPTION",
                ])

            # Write outputs
            write_csv(
                os.path.join(REPORT_DIR, f"missing_driver_numbers_safety_summary_{DATE_SUFFIX}.csv"),
                ["metric", "value"],
                [
                    ["missing_driver_number_charters", len(candidates)],
                    ["safe_count_zero_charges_or_cancelled", safe_count],
                    ["exception_count_has_charges_and_not_cancelled", exception_count],
                ],
            )
            write_csv(
                os.path.join(REPORT_DIR, f"missing_driver_numbers_safety_details_{DATE_SUFFIX}.csv"),
                ["charter_id", "driver", "status", "booking_status", "charges_count", "assessment"],
                details_rows,
            )

            print("=== Missing Driver Numbers Safety Audit ===")
            print(f"Total with non-employee driver number: {len(candidates)}")
            print(f"SAFE (zero charges OR cancelled): {safe_count}")
            print(f"EXCEPTIONS (has charges AND not cancelled): {exception_count}")
            print("Outputs written under reports/ with date suffix.")


if __name__ == "__main__":
    main()
