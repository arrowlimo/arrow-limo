#!/usr/bin/env python3
"""
Apply approved (or high-confidence) driver_name → employee_id mappings to staging_driver_pay.

- Dry-run by default; use --write to persist.
- By default only uses rows in driver_name_employee_map with status='approved'.
- Optional: --auto-approve-threshold N.NN treats suggestions with confidence>=threshold
  as approved for this run (no change to the mapping table status).
- Updates only rows where staging_driver_pay.employee_id IS NULL and driver_name present.

Usage:
  python -X utf8 scripts/apply_driver_pay_mapping_to_staging.py [--write] [--auto-approve-threshold 0.98]
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
    parser.add_argument('--auto-approve-threshold', type=float, default=None,
                        help='Temporarily treat suggestions with confidence>=threshold as approved for this run')
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Basic checks
    for tbl in ('staging_driver_pay','driver_name_employee_map'):
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s) AS ok", (tbl,))
        if not cur.fetchone()['ok']:
            print(f"FAIL: table {tbl} not found")
            return

    # Determine if staging has an employee_id column; if not, we will use a link table
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'staging_driver_pay'
        """
    )
    sdp_cols = {r['column_name'] for r in cur.fetchall()}
    has_employee_id_col = 'employee_id' in sdp_cols

    # Ensure we have a primary key to link on
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'staging_driver_pay' AND column_name = 'id'
    """)
    has_id = cur.fetchone() is not None
    if not has_employee_id_col and not has_id:
        print("FAIL: staging_driver_pay lacks both employee_id and id columns; cannot proceed safely.")
        return

    if has_employee_id_col:
        cur.execute("SELECT COUNT(*) AS c FROM staging_driver_pay WHERE employee_id IS NULL AND TRIM(COALESCE(driver_name,'')) <> ''")
        targetable = cur.fetchone()['c']
        print(f"Targetable staging rows (employee_id is NULL and name present): {targetable}")
        print("Mode: direct column update")
    else:
        # Using link table strategy
        print("Mode: link table (staging_driver_pay_links)")
        # Create link table if not exists
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS staging_driver_pay_links (
                staging_id INTEGER PRIMARY KEY,
                employee_id INTEGER NOT NULL,
                method TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Count targetable rows (no existing link)
        cur.execute(
            """
            SELECT COUNT(*) AS c
            FROM staging_driver_pay s
            LEFT JOIN staging_driver_pay_links l ON l.staging_id = s.id
            WHERE l.staging_id IS NULL
              AND TRIM(COALESCE(s.driver_name,'')) <> ''
            """
        )
        targetable = cur.fetchone()['c']
        print(f"Targetable staging rows (no existing link and name present): {targetable}")

    auto_clause = ''
    params = []
    if args.auto_approve_threshold is not None:
        auto_clause = " OR (status = 'suggested' AND confidence >= %s)"
        params.append(args.auto_approve_threshold)

    # Preview joinable count
    if has_employee_id_col:
        cur.execute(
            f"""
            WITH m AS (
                SELECT normalized_name, candidate_employee_id
                FROM driver_name_employee_map
                WHERE status = 'approved' {auto_clause}
                  AND candidate_employee_id IS NOT NULL
            )
            SELECT COUNT(*) AS c
            FROM staging_driver_pay s
            JOIN m ON lower(regexp_replace(COALESCE(s.driver_name,''), '[\n\r\t ,;:_\.-]+', ' ', 'g')) = m.normalized_name
            WHERE s.employee_id IS NULL
            """,
            params
        )
    else:
        cur.execute(
            f"""
            WITH m AS (
                SELECT normalized_name, candidate_employee_id
                FROM driver_name_employee_map
                WHERE status = 'approved' {auto_clause}
                  AND candidate_employee_id IS NOT NULL
            )
            SELECT COUNT(*) AS c
            FROM staging_driver_pay s
            LEFT JOIN staging_driver_pay_links l ON l.staging_id = s.id
            JOIN m ON lower(regexp_replace(COALESCE(s.driver_name,''), '[\n\r\t ,;:_\.-]+', ' ', 'g')) = m.normalized_name
            WHERE l.staging_id IS NULL
            """,
            params
        )
    joinable = cur.fetchone()['c']
    print(f"Joinable by approved mapping: {joinable}")

    if joinable == 0:
        print("No rows to update via approved mapping. PASS (no-op)")
        return

    if not args.write:
        print("Dry-run only. Use --write to apply.")
        return

    # Apply update
    if has_employee_id_col:
        cur.execute(
            f"""
            WITH m AS (
                SELECT normalized_name, candidate_employee_id
                FROM driver_name_employee_map
                WHERE status = 'approved' {auto_clause}
                  AND candidate_employee_id IS NOT NULL
            )
            UPDATE staging_driver_pay s
            SET employee_id = m.candidate_employee_id
            FROM m
            WHERE s.employee_id IS NULL
              AND lower(regexp_replace(COALESCE(s.driver_name,''), '[\n\r\t ,;:_\.-]+', ' ', 'g')) = m.normalized_name
            """,
            params
        )
        updated = cur.rowcount
    else:
        # Insert links for unmatched rows
        cur.execute(
            f"""
            WITH m AS (
                SELECT normalized_name, candidate_employee_id
                FROM driver_name_employee_map
                WHERE status = 'approved' {auto_clause}
                  AND candidate_employee_id IS NOT NULL
            ),
            to_insert AS (
                SELECT s.id AS staging_id, m.candidate_employee_id AS employee_id
                FROM staging_driver_pay s
                LEFT JOIN staging_driver_pay_links l ON l.staging_id = s.id
                JOIN m ON lower(regexp_replace(COALESCE(s.driver_name,''), '[\n\r\t ,;:_\.-]+', ' ', 'g')) = m.normalized_name
                WHERE l.staging_id IS NULL
            )
            INSERT INTO staging_driver_pay_links (staging_id, employee_id, method, notes)
            SELECT staging_id, employee_id, 'name_mapping', 'auto-approve-threshold applied'
            FROM to_insert
            ON CONFLICT (staging_id) DO UPDATE SET employee_id = EXCLUDED.employee_id
            """,
            params
        )
        updated = cur.rowcount
    conn.commit()
    print(f"Updated staging rows: {updated}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
