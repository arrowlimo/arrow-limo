"""
Link `charters.vehicle_id` using the textual `charters.vehicle` field.

Approach:
- Normalize vehicle labels (e.g., L-10, L10, L 10 -> L10) and compare against
  `vehicles.unit_number` similarly normalized. Also try license_plate.

Safety:
- Dry-run by default; use --write to apply.
- Only update NULL vehicle_id where we have an exact single match.
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
    pwd = os.getenv('DB_PASSWORD', '***REDACTED***')
    return psycopg2.connect(host=host, database=db, user=user, password=pwd)


def norm(s: str) -> str:
    if s is None:
        return ''
    s = s.strip().upper()
    # remove non-alphanumeric
    s = re.sub(r'[^A-Z0-9]', '', s)
    # unify leading L prefix patterns like L-10 -> L10
    return s


def load_vehicle_index(cur):
    cur.execute("SELECT vehicle_id, unit_number, license_plate FROM vehicles")
    idx = {}
    plate_idx = {}
    for r in cur.fetchall():
        key = norm(r['unit_number'] or '')
        if key:
            idx[key] = r['vehicle_id']
        pkey = norm(r['license_plate'] or '')
        if pkey:
            plate_idx[pkey] = r['vehicle_id']
    return idx, plate_idx


def find_charter_targets(cur):
    cur.execute(
        """
        SELECT charter_id, reserve_number, vehicle
        FROM charters
        WHERE vehicle_id IS NULL
          AND vehicle IS NOT NULL
          AND vehicle <> ''
        """
    )
    return cur.fetchall()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Apply updates')
    parser.add_argument('--limit', type=int, default=None, help='Limit rows processed')
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    v_idx, p_idx = load_vehicle_index(cur)
    rows = find_charter_targets(cur)
    total = len(rows)
    if args.limit is not None:
        rows = rows[: args.limit]
    print(f"Found {total} charters with missing vehicle_id and a vehicle label; previewing {len(rows)}")

    updates = []
    for r in rows:
        label = norm(r['vehicle'])
        vid = v_idx.get(label)
        if not vid and label.startswith('L') and label[1:].isdigit():
            # accept LNN patterns
            vid = v_idx.get(label)
        if not vid:
            # try by plate
            vid = p_idx.get(label)
        if vid:
            updates.append((vid, r['charter_id'], r['reserve_number'], r['vehicle']))

    print(f"Resolvable matches (exact normalization): {len(updates)}")
    preview = min(10, len(updates))
    for i in range(preview):
        vid, cid, rsv, veh = updates[i]
        print(f"  charter_id={cid} reserve={rsv} vehicle='{veh}' -> vehicle_id={vid}")

    if not args.write:
        print("\nDRY-RUN: No updates written. Use --write to apply.")
        cur.close(); conn.close(); return

    applied = 0
    for vid, cid, _, _ in updates:
        cur.execute("UPDATE charters SET vehicle_id = %s WHERE charter_id = %s AND vehicle_id IS NULL", (vid, cid))
        applied += cur.rowcount
    conn.commit()
    print(f"\nAPPLIED: Updated vehicle_id on {applied} charters.")

    cur.close(); conn.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
