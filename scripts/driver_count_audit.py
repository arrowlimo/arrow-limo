#!/usr/bin/env python3
"""Driver count audit: compare permissive vs tightened filters and show duplicates.

Outputs:
- reports/driver_count_audit_summary_<DATE>.csv
- reports/driver_count_audit_duplicates_employee_id_<DATE>.csv
- reports/driver_count_audit_duplicates_name_<DATE>.csv
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

def get_existing_columns(cur, table_name: str = "employees") -> set:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table_name,),
    )
    return {r[0] for r in cur.fetchall()}

def build_permissive_filter(cols: set) -> str:
    parts = []
    for field in ("role", "position", "employee_type"):
        if field in cols:
            parts.append(f"LOWER(COALESCE({field}, '')) = 'driver'")
    # Fallback to is_chauffeur if text fields missing
    if not parts and "is_chauffeur" in cols:
        parts.append("COALESCE(is_chauffeur, false) = true")
    return " OR ".join(parts) if parts else "TRUE"  # never error

def build_tightened_filter(cols: set) -> str:
    role_parts = []
    if "is_chauffeur" in cols:
        role_parts.append("COALESCE(is_chauffeur, false) = true")
    for field in ("role", "position", "employee_type"):
        if field in cols:
            role_parts.append(f"LOWER(COALESCE({field}, '')) = 'driver'")
    role_clause = " OR ".join(role_parts) if role_parts else "TRUE"
    status_clause = ""
    if "status" in cols:
        status_clause = " AND COALESCE(status, 'active') IN ('active','current')"
    name_clause = ""
    if "full_name" in cols:
        name_clause = " AND COALESCE(TRIM(full_name), '') <> ''"
    return f"({role_clause}){status_clause}{name_clause}"

def write_csv(path: str, headers, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if headers:
            w.writerow(headers)
        w.writerows(rows)


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    with psycopg2.connect(**PG) as conn:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            # Total employees
            cur.execute("SELECT COUNT(*) FROM employees")
            total_employees = cur.fetchone()[0] or 0

            cols = get_existing_columns(cur, "employees")
            permissive_filter = build_permissive_filter(cols)
            tightened_filter = build_tightened_filter(cols)

            # Permissive set (original API-style filter)
            cur.execute(
                f"SELECT employee_id, full_name, status FROM employees WHERE {permissive_filter}"
            )
            permissive_rows = cur.fetchall()
            permissive_count_rows = len(permissive_rows)
            cur.execute(
                f"SELECT COUNT(DISTINCT employee_id) FROM employees WHERE {permissive_filter}"
            )
            permissive_distinct_ids = cur.fetchone()[0] or 0

            # Tightened set (new API filter)
            cur.execute(
                f"SELECT COUNT(DISTINCT employee_id) FROM employees WHERE {tightened_filter}"
            )
            tightened_distinct_ids = cur.fetchone()[0] or 0

            # Duplicates by employee_id within permissive set
            cur.execute(
                f"""
                SELECT employee_id,
                       COUNT(*) AS rows,
                       MAX(full_name) AS sample_name,
                       STRING_AGG(DISTINCT COALESCE(status,'unknown'), ',') AS statuses
                FROM employees
                WHERE {permissive_filter}
                GROUP BY employee_id
                HAVING COUNT(*) > 1
                ORDER BY rows DESC, employee_id
                LIMIT 100
                """
            )
            dup_ids = cur.fetchall()

            # Duplicates by normalized name within permissive set
            cur.execute(
                f"""
                SELECT LOWER(TRIM(COALESCE(full_name,''))) AS norm_name,
                       COUNT(*) AS rows
                FROM employees
                WHERE {permissive_filter}
                  AND COALESCE(TRIM(full_name),'') <> ''
                GROUP BY 1
                HAVING COUNT(*) > 1
                ORDER BY rows DESC, norm_name
                LIMIT 100
                """
            )
            dup_names = cur.fetchall()

            # Write summary CSV
            summary_rows = [
                ["date", DATE_SUFFIX],
                ["total_employees", total_employees],
                ["permissive_rows", permissive_count_rows],
                ["permissive_distinct_employee_id", permissive_distinct_ids],
                ["tightened_distinct_employee_id", tightened_distinct_ids],
                ["duplicate_employee_id_count", len(dup_ids)],
                ["duplicate_normalized_name_count", len(dup_names)],
            ]
            write_csv(
                os.path.join(
                    REPORT_DIR,
                    f"driver_count_audit_summary_{DATE_SUFFIX}.csv",
                ),
                ["metric", "value"],
                summary_rows,
            )

            # Write duplicate employee_id CSV
            write_csv(
                os.path.join(
                    REPORT_DIR,
                    f"driver_count_audit_duplicates_employee_id_{DATE_SUFFIX}.csv",
                ),
                ["employee_id", "rows", "sample_name", "statuses"],
                dup_ids,
            )

            # Write duplicate normalized name CSV
            write_csv(
                os.path.join(
                    REPORT_DIR,
                    f"driver_count_audit_duplicates_name_{DATE_SUFFIX}.csv",
                ),
                ["normalized_name", "rows"],
                dup_names,
            )

            # Console summary
            print("=== Driver Count Audit ===")
            print(f"Total employees: {total_employees}")
            print(f"Permissive rows (OR filter): {permissive_count_rows}")
            print(f"Permissive distinct employee_id: {permissive_distinct_ids}")
            print(f"Tightened distinct employee_id: {tightened_distinct_ids}")
            print(f"Duplicate employee_id (top {len(dup_ids)} listed):")
            for row in dup_ids[:10]:
                print(f"  ID {row[0]}: {row[1]} rows; name={row[2]!s}; statuses={row[3]!s}")
            print(f"Duplicate normalized names (top {len(dup_names)} listed):")
            for row in dup_names[:10]:
                print(f"  name={row[0]!s}: {row[1]} rows")
            print("Outputs written under reports/ with date suffix.")


if __name__ == "__main__":
    main()
