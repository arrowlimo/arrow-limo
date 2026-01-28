"""Detect charters with multiple drivers (training) and optionally update secondary driver fields.

Heuristic:
- Use driver_payroll.charter_id to find charters with >1 distinct employee_id in the same month.
- Propose the most frequent/earlier driver as primary (existing assigned_driver_id) and the other as secondary.

Usage:
  python -X utf8 scripts/detect_training_charters.py --year 2012 --apply

By default, dry-run prints proposals. With --apply, updates charters.secondary_driver_id/name.
"""

from __future__ import annotations

import argparse
import os
from collections import defaultdict

import psycopg2
import psycopg2.extras


def get_db_connection():
    host = os.getenv("DB_HOST", "localhost")
    name = os.getenv("DB_NAME", "almsdata")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "***REMOVED***")
    return psycopg2.connect(host=host, dbname=name, user=user, password=password)


def employee_name_map(conn):
    cur = conn.cursor()
    cur.execute("SELECT employee_id, full_name FROM employees")
    out = {int(eid): (name or "") for eid, name in cur.fetchall() if eid is not None}
    cur.close(); return out


def main():
    ap = argparse.ArgumentParser(description="Detect and update training charters with secondary driver")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = get_db_connection()
    names = employee_name_map(conn)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # Find charters with multiple employees contributing payroll in the year
    cur.execute(
        """
        SELECT charter_id, array_agg(DISTINCT employee_id) AS drivers
        FROM driver_payroll
        WHERE year=%s AND employee_id IS NOT NULL AND charter_id IS NOT NULL
          AND (payroll_class IS NULL OR payroll_class IN ('WAGE','BACKFILL'))
        GROUP BY charter_id
        HAVING COUNT(DISTINCT employee_id) > 1
        """,
        (args.year,),
    )
    rows = cur.fetchall()
    proposals = []
    for r in rows:
        cid = int(r['charter_id'])
        drivers = [int(x) for x in r['drivers'] if x is not None]
        # Read current assigned_driver_id
        c2 = conn.cursor()
        c2.execute("SELECT assigned_driver_id, secondary_driver_id FROM charters WHERE charter_id=%s", (cid,))
        row = c2.fetchone(); c2.close()
        if not row:
            continue
        primary = row[0]
        secondary_existing = row[1]
        # Choose secondary as the other driver (any not equal to primary)
        candidates = [d for d in drivers if d != primary]
        if not candidates:
            continue
        secondary = candidates[0]
        proposals.append((cid, primary, secondary))

    if not args.apply:
        print(f"Found {len(proposals)} charters with multiple drivers (training candidates)")
        for cid, primary, secondary in proposals[:50]:
            print(f"Charter {cid}: primary={primary} ({names.get(primary,'')}), secondary={secondary} ({names.get(secondary,'')})")
        return

    # Apply updates
    updated = 0
    u = conn.cursor()
    for cid, primary, secondary in proposals:
        secname = names.get(secondary, None)
        u.execute(
            "UPDATE charters SET secondary_driver_id=%s, secondary_driver_name=%s WHERE charter_id=%s",
            (secondary, secname, cid),
        )
        updated += u.rowcount
    conn.commit(); u.close(); conn.close()
    print(f"Updated {updated} charters with secondary driver info.")


if __name__ == "__main__":
    main()
