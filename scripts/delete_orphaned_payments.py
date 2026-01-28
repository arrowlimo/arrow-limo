"""
Delete orphaned payments (payments with reserve_numbers not in charters table).

Backs up payments before deletion, requires override key.
"""
import os
import sys
import argparse
from datetime import datetime
import psycopg2
from table_protection import protect_deletion, create_backup_before_delete, require_write_mode, log_deletion_audit


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


def get_fk_references(cur, schema: str, table: str):
    cur.execute(
        """
        SELECT
            tc.table_name AS fk_table,
            kcu.column_name AS fk_column
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_schema = %s
          AND ccu.table_name = %s
          AND ccu.column_name = 'payment_id'
        ORDER BY fk_table
        """,
        (schema, table)
    )
    return [(r[0], r[1]) for r in cur.fetchall()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply deletion (default dry-run)')
    ap.add_argument('--override-key', help='Override key for deleting from protected payments table')
    args = ap.parse_args()

    conn = connect(); conn.autocommit = False
    cur = conn.cursor()

    protect_deletion('payments', dry_run=not args.write, override_key=args.override_key)

    pcols = columns(cur, 'payments')
    amount_col = 'amount' if 'amount' in pcols else ('payment_amount' if 'payment_amount' in pcols else None)
    date_col = None
    for cand in ('payment_date', 'created_at', 'last_updated', 'updated_at'):
        if cand in pcols:
            date_col = cand
            break
    if not amount_col or not date_col:
        print('Required columns not found.')
        return

    # Find orphaned payments
    cur.execute(
        f"""
        SELECT p.payment_id, p.reserve_number, COALESCE(p.{amount_col},0) AS amount,
               CAST(p.{date_col} AS DATE) AS pdate,
               COALESCE(p.payment_method,'') AS payment_method,
               COALESCE(p.payment_key,'') AS payment_key
        FROM payments p
        WHERE p.reserve_number IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
          )
        ORDER BY pdate
        """
    )
    orphaned = cur.fetchall()

    if not orphaned:
        print('No orphaned payments found.')
        conn.rollback(); cur.close(); conn.close(); return

    print(f"Found {len(orphaned)} orphaned payments:\n")
    for pid, rn, amt, pdate, method, pkey in orphaned:
        print(f"  payment_id={pid} reserve_number={rn} amount={amt} date={pdate} method={method} key={pkey}")

    if not require_write_mode(args):
        conn.rollback(); cur.close(); conn.close(); return

    try:
        id_list = [t[0] for t in orphaned]
        
        # Get and handle FK dependencies
        fk_refs = get_fk_references(cur, 'public', 'payments')
        for fk_table, fk_col in fk_refs:
            cur.execute(f"SELECT COUNT(*) FROM {fk_table} WHERE {fk_col} = ANY(%s)", (id_list,))
            cnt = cur.fetchone()[0]
            if cnt > 0:
                create_backup_before_delete(cur, fk_table, condition=f"{fk_col} IN ({','.join(str(x) for x in id_list)})")
                cur.execute(f"DELETE FROM {fk_table} WHERE {fk_col} = ANY(%s)", (id_list,))
                print(f"Deleted {cur.rowcount} rows from {fk_table}")
        
        # Backup
        create_backup_before_delete(cur, 'payments', condition=f"payment_id IN ({','.join(str(x) for x in id_list)})")

        # Delete
        cur.execute(f"DELETE FROM payments WHERE payment_id = ANY(%s)", (id_list,))
        deleted = cur.rowcount
        conn.commit()

        log_deletion_audit('payments', deleted, condition=f"payment_id IN ({','.join(str(x) for x in id_list)})")
        print(f"\n✓ Deleted {deleted} orphaned payments")

    except Exception as e:
        conn.rollback()
        print(f"Failed: {e}", file=sys.stderr)
        sys.exit(2)
    finally:
        cur.close(); conn.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Failed: {e}", file=sys.stderr)
        sys.exit(2)
