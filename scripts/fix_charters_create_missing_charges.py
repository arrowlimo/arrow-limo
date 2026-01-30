"""
Create missing charter_charges for charters that have a positive
total_amount_due but zero charge rows.

Safety:
- Dry-run by default. Use --write to apply.
- Idempotent: inserts only when no charges exist for the charter_id.
- Tracks inserted rows and prints a summary.

Business rules from repo guidance:
- Do not touch payments here; only charges for charters with amount>0.
- Keep it simple: single charge line equal to total_amount_due.
"""
import argparse
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    host = os.getenv('DB_HOST', 'localhost')
    db = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    pwd = os.getenv('DB_PASSWORD', '***REDACTED***')
    return psycopg2.connect(host=host, database=db, user=user, password=pwd)


def find_targets(cur):
    cur.execute(
        """
        SELECT c.charter_id, c.reserve_number, c.total_amount_due
        FROM charters c
        WHERE c.total_amount_due IS NOT NULL
          AND c.total_amount_due > 0
          AND NOT EXISTS (
                SELECT 1 FROM charter_charges cc
                WHERE cc.charter_id = c.charter_id
          )
        ORDER BY c.total_amount_due DESC, c.charter_id
        """
    )
    return cur.fetchall()


def ensure_charge_columns(cur):
    # Discover available columns to avoid schema mismatch
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'charter_charges'
        """
    )
    return {r['column_name'] for r in cur.fetchall()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Apply changes')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of rows to process')
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("\nCreate missing charter_charges for charters with total_amount_due>0 and no charges")
    targets = find_targets(cur)
    total = len(targets)
    if args.limit is not None:
        targets = targets[: args.limit]
    print(f"Found {total} candidate charters; previewing {len(targets)}")

    if not targets:
        print("No work to do.")
        cur.close(); conn.close()
        return

    cols = ensure_charge_columns(cur)
    # Build insert statement based on available columns
    # Minimal required columns we try to populate
    insert_cols = ['charter_id', 'description', 'amount']
    if 'created_at' in cols:
        insert_cols.append('created_at')
    if 'updated_at' in cols:
        insert_cols.append('updated_at')

    placeholders = ','.join(['%s'] * len(insert_cols))
    insert_sql = f"INSERT INTO charter_charges ({', '.join(insert_cols)}) VALUES ({placeholders})"

    to_insert = []
    for row in targets:
        desc = 'Charter total (auto-generated)'
        vals = [row['charter_id'], desc, float(row['total_amount_due'])]
        # Fill timestamps as NULLs; DB default may set them
        if 'created_at' in cols:
            vals.append(None)
        if 'updated_at' in cols:
            vals.append(None)
        to_insert.append((row['charter_id'], row['reserve_number'], row['total_amount_due'], vals))

    preview = min(10, len(to_insert))
    print("\nPreview (first up to 10):")
    for i in range(preview):
        cid, rsv, amt, _ = to_insert[i]
        print(f"  charter_id={cid} reserve={rsv} amount=${amt:,.2f}")

    if not args.write:
        print("\nDRY-RUN: No changes written. Run with --write to apply.")
        cur.close(); conn.close()
        return

    inserted = 0
    for _, _, _, vals in to_insert:
        cur.execute(insert_sql, vals)
        inserted += 1

    conn.commit()
    print(f"\nAPPLIED: Inserted {inserted} charter_charges rows.")

    cur.close(); conn.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
