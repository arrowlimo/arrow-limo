"""
Ensure vehicles table has unit_number entries L-1 through L-25.

Safety:
- Dry-run by default; use --write to apply.
- Idempotent: inserts only missing L-series unit_numbers.
- Uses schema introspection to insert only available columns.
"""
import argparse
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def get_vehicle_columns(cur):
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'vehicles'
        """
    )
    return {r['column_name'] for r in cur.fetchall()}


def existing_l_series(cur):
    cur.execute("SELECT unit_number FROM vehicles WHERE unit_number ILIKE 'L-%'")
    return { (r['unit_number'] or '').strip().upper() for r in cur.fetchall() }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply inserts')
    args = ap.parse_args()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cols = get_vehicle_columns(cur)
    have = existing_l_series(cur)

    targets = [f"L-{i}" for i in range(1, 26)]
    missing = [u for u in targets if u not in have]

    print(f"Existing L-series count: {len(have)}")
    print(f"Missing L-series to create: {len(missing)}")
    if missing:
        print("First few missing:")
        for u in missing[:10]:
            print(f"  {u}")

    if not missing:
        print("Nothing to insert.")
        cur.close(); conn.close(); return

    # Prepare insert statement for available columns
    insert_cols = ['unit_number']
    # Add minimal helpful columns if they exist
    for opt in ['vehicle_type', 'status', 'created_at', 'updated_at']:
        if opt in cols:
            insert_cols.append(opt)

    placeholders = ','.join(['%s'] * len(insert_cols))
    sql = f"INSERT INTO vehicles ({', '.join(insert_cols)}) VALUES ({placeholders})"

    if not args.write:
        print("\nDRY-RUN: Would insert these unit_numbers:")
        for u in missing:
            print(f"  {u}")
        cur.close(); conn.close(); return

    inserted = 0
    for u in missing:
        # Build values vector
        vals = [u]
        if 'vehicle_type' in insert_cols:
            vals.append('limousine')
        if 'status' in insert_cols:
            vals.append('active')
        if 'created_at' in insert_cols:
            vals.append(None)
        if 'updated_at' in insert_cols:
            vals.append(None)
        cur.execute(sql, vals)
        inserted += 1

    conn.commit()
    print(f"Inserted {inserted} vehicle rows for L-series.")

    cur.close(); conn.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
