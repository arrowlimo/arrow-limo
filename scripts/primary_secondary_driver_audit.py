#!/usr/bin/env python3
"""Audit primary vs secondary driver classification.

Primary: employees with employee_number LIKE 'Dr%' and status in active/current.
Secondary: employees not Dr% but marked as driver by flags/roles, status in active/current.

Outputs:
- reports/primary_secondary_driver_audit_summary_<DATE>.csv
- reports/primary_driver_list_<DATE>.csv
- reports/secondary_driver_list_<DATE>.csv
- reports/misclassified_chauffeurs_<DATE>.csv  (is_chauffeur=true but not Dr%)
"""
import csv
import datetime
import os
import psycopg2

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


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    with psycopg2.connect(**PG) as conn:
        with conn.cursor() as cur:
            # Primary drivers (Dr%)
            cur.execute(
                """
                SELECT employee_id, full_name, employee_number
                FROM employees
                WHERE employee_number LIKE 'Dr%'
                  AND COALESCE(status, 'active') IN ('active','current')
                ORDER BY employee_number
                """
            )
            primary = cur.fetchall()

            # Secondary drivers (non-Dr% but driver flags)
            # Build dynamic OR for role fields present
            flags = ["COALESCE(is_chauffeur, false) = true"]
            # Check which columns exist
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='employees'")
            cols = {r[0] for r in cur.fetchall()}
            if 'position' in cols:
                flags.append("LOWER(COALESCE(position,'')) = 'driver'")
            if 'role' in cols:
                flags.append("LOWER(COALESCE(role,'')) = 'driver'")
            if 'employee_type' in cols:
                flags.append("LOWER(COALESCE(employee_type,'')) = 'driver'")
            or_clause = " OR ".join(flags)

            cur.execute(
                f"""
                SELECT employee_id, full_name, employee_number
                FROM employees
                WHERE employee_number IS NOT NULL
                  AND TRIM(employee_number) <> ''
                  AND employee_number NOT LIKE 'Dr%'
                  AND ({or_clause})
                  AND COALESCE(status, 'active') IN ('active','current')
                ORDER BY employee_number
                """
            )
            secondary = cur.fetchall()

            # Misclassified chauffeurs: is_chauffeur true but non-Dr%
            cur.execute(
                """
                SELECT employee_id, full_name, employee_number
                FROM employees
                WHERE COALESCE(is_chauffeur, false) = true
                  AND employee_number NOT LIKE 'Dr%'
                  AND COALESCE(status, 'active') IN ('active','current')
                ORDER BY employee_number
                """
            )
            misclassified = cur.fetchall()

            # Write files
            write_csv(
                os.path.join(REPORT_DIR, f"primary_secondary_driver_audit_summary_{DATE_SUFFIX}.csv"),
                ["metric", "value"],
                [
                    ["primary_count", len(primary)],
                    ["secondary_count", len(secondary)],
                    ["misclassified_chauffeurs", len(misclassified)],
                ],
            )
            write_csv(
                os.path.join(REPORT_DIR, f"primary_driver_list_{DATE_SUFFIX}.csv"),
                ["employee_id", "full_name", "employee_number"],
                primary,
            )
            write_csv(
                os.path.join(REPORT_DIR, f"secondary_driver_list_{DATE_SUFFIX}.csv"),
                ["employee_id", "full_name", "employee_number"],
                secondary,
            )
            write_csv(
                os.path.join(REPORT_DIR, f"misclassified_chauffeurs_{DATE_SUFFIX}.csv"),
                ["employee_id", "full_name", "employee_number"],
                misclassified,
            )
            print("=== Primary/Secondary Driver Audit ===")
            print(f"Primary: {len(primary)}; Secondary: {len(secondary)}; Misclassified: {len(misclassified)}")
            print("Outputs under reports/ with date suffix.")


if __name__ == "__main__":
    main()
