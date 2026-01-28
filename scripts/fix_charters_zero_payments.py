"""
Fix charters with paid_amount but no actual payments (zero out paid_amount, recalc balance).

Targets charters where:
- paid_amount != 0 but SUM(payments by reserve_number) = 0 or NULL

Dry-run by default; use --write to apply with backup.
"""
import os
import sys
import argparse
from datetime import datetime
import psycopg2


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    )


def columns(cur, table: str):
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
        """,
        (table,)
    )
    return [r[0] for r in cur.fetchall()]


def create_backup(cur, condition: str):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"charters_backup_paid_zero_{ts}"
    cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM charters WHERE {condition}")
    cur.execute(f"SELECT COUNT(*) FROM {backup_name}")
    cnt = cur.fetchone()[0]
    print(f"✓ Created backup: {backup_name} ({cnt} rows)")
    return backup_name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply changes (default dry-run)')
    ap.add_argument('--backup', action='store_true', help='Create backup before changes')
    args = ap.parse_args()

    conn = connect(); conn.autocommit = False
    cur = conn.cursor()

    pcols = columns(cur, 'payments')
    amount_col = 'amount' if 'amount' in pcols else ('payment_amount' if 'payment_amount' in pcols else None)
    if not amount_col:
        print('Required columns not found.')
        return

    # Find charters with paid_amount != 0 but no payment sum
    cur.execute(
        f"""
        WITH payment_sums AS (
          SELECT reserve_number, ROUND(SUM(COALESCE({amount_col},0))::numeric,2) AS paid
          FROM payments
          WHERE reserve_number IS NOT NULL
          GROUP BY reserve_number
        )
        SELECT c.charter_id, c.reserve_number,
               ROUND(COALESCE(c.paid_amount,0)::numeric,2) AS paid_field,
               COALESCE(ps.paid,0) AS paid_sum,
               ROUND(COALESCE(c.total_amount_due,0)::numeric,2) AS total_due
        FROM charters c
        LEFT JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
        WHERE ROUND(COALESCE(c.paid_amount,0)::numeric,2) != 0
          AND COALESCE(ps.paid,0) = 0
        ORDER BY c.reserve_number
        """
    )
    targets = cur.fetchall()

    if not targets:
        print('No mismatches found.')
        conn.rollback(); cur.close(); conn.close(); return

    print(f"Found {len(targets)} charters with paid_amount but no payments:\n")
    for cid, rn, pf, ps, td in targets[:10]:
        print(f"  {rn}: paid_field={pf}, paid_sum={ps}, total_due={td}")
    if len(targets) > 10:
        print(f"  ... and {len(targets)-10} more")

    if not args.write:
        print('\nDRY-RUN: No changes applied. Use --write to apply.')
        conn.rollback(); cur.close(); conn.close(); return

    # Backup if requested
    if args.backup:
        rn_list = ','.join(f"'{t[1]}'" for t in targets)
        create_backup(cur, f"reserve_number IN ({rn_list})")

    # Zero out paid_amount and set balance = total_amount_due
    for cid, rn, pf, ps, td in targets:
        cur.execute(
            """
            UPDATE charters
            SET paid_amount = 0,
                balance = ROUND(COALESCE(total_amount_due,0)::numeric,2)
            WHERE charter_id = %s
            """,
            (cid,)
        )

    conn.commit()
    print(f"\n✓ Updated {len(targets)} charters: zeroed paid_amount, set balance = total_amount_due")

    cur.close(); conn.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Failed: {e}", file=sys.stderr)
        sys.exit(2)
