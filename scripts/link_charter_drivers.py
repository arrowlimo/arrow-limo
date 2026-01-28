"""
Link `charters.assigned_driver_id` (and optionally employee_id) from `charters.driver` when the
driver field appears to contain an employee_number like DR117 / Dr100 / 117.

Safety:
- Dry-run by default; use --write to apply.
- Only updates rows with NULL assigned_driver_id.
- Exact numeric extraction match to employees.employee_number; no fuzzy names here.
"""
import argparse
import os
import re
import sys
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    host = os.getenv('DB_HOST', 'localhost')
    db = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    pwd = os.getenv('DB_PASSWORD', '***REMOVED***')
    return psycopg2.connect(host=host, database=db, user=user, password=pwd)


def extract_number(token: str):
    if not token:
        return None
    m = re.search(r'(\d+)', token)
    return m.group(1) if m else None


def load_employee_index(cur):
    cur.execute("SELECT employee_id, employee_number, full_name FROM employees")
    idx = {}
    for r in cur.fetchall():
        if r['employee_number'] is not None:
            idx[str(r['employee_number'])] = r['employee_id']
    return idx


def find_charters(cur):
    cur.execute(
        """
        SELECT charter_id, reserve_number, driver
        FROM charters
        WHERE assigned_driver_id IS NULL
          AND driver IS NOT NULL AND driver <> ''
        """
    )
    return cur.fetchall()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Apply updates')
    parser.add_argument('--limit', type=int, default=None, help='Limit processed rows')
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    emp_idx = load_employee_index(cur)
    rows = find_charters(cur)
    total = len(rows)
    if args.limit is not None:
        rows = rows[: args.limit]
    print(f"Found {total} charters missing assigned_driver_id with a driver label; previewing {len(rows)}")

    updates = []
    for r in rows:
        num = extract_number(r['driver'])
        if not num:
            continue
        emp_id = emp_idx.get(str(num))
        if emp_id:
            updates.append((emp_id, r['charter_id'], r['reserve_number'], r['driver']))

    print(f"Resolvable exact matches via employee_number: {len(updates)}")
    preview = min(10, len(updates))
    for i in range(preview):
        emp_id, cid, rsv, drv = updates[i]
        print(f"  charter_id={cid} reserve={rsv} driver='{drv}' -> assigned_driver_id={emp_id}")

    if not args.write:
        print("\nDRY-RUN: No updates written. Use --write to apply.")
        cur.close(); conn.close(); return

    applied = 0
    for emp_id, cid, _, _ in updates:
        cur.execute(
            "UPDATE charters SET assigned_driver_id = %s WHERE charter_id = %s AND assigned_driver_id IS NULL",
            (emp_id, cid),
        )
        applied += cur.rowcount
    conn.commit()
    print(f"\nAPPLIED: Updated assigned_driver_id on {applied} charters.")

    cur.close(); conn.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
