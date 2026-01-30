import os
import sys
from datetime import datetime

import psycopg2

from verify_lms_reserve_client_consistency import build_combined_lms_mapping


def get_conn():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        dbname=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REDACTED***'),
    )


def main(write=False):
    conn = get_conn()
    cur = conn.cursor()

    # Gather target charters with NULL client_id but with an account_number we can map
    cur.execute(
        """
        SELECT c.reserve_number, c.account_number
        FROM charters c
        WHERE c.client_id IS NULL AND c.account_number IS NOT NULL AND TRIM(c.account_number) <> ''
        ORDER BY c.reserve_number
        """
    )
    targets = cur.fetchall()
    print(f"Null-client charters with account_number: {len(targets)}")

    # Preview how many have a matching client account
    cur.execute(
        """
        SELECT COUNT(*)
        FROM charters c
        JOIN clients cl ON TRIM(cl.account_number) = TRIM(c.account_number)
        WHERE c.client_id IS NULL AND c.account_number IS NOT NULL AND TRIM(c.account_number) <> ''
        """
    )
    can_link = cur.fetchone()[0]
    print(f"Can link by account_number -> clients: {can_link}")

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = f"charters_backup_link_by_account_{ts}"

    if write and can_link:
        # Backup affected rows
        cur.execute(
            f"""
            CREATE TABLE {backup} AS
            SELECT * FROM charters c
            WHERE c.client_id IS NULL AND c.account_number IS NOT NULL AND TRIM(c.account_number) <> ''
            AND EXISTS (SELECT 1 FROM clients cl WHERE TRIM(cl.account_number) = TRIM(c.account_number))
            """
        )
        print(f"Backup created: {backup}")

        # Update links by account_number
        cur.execute(
            """
            UPDATE charters c
            SET client_id = cl.client_id,
                client_display_name = COALESCE(cl.client_name, cl.company_name)
            FROM clients cl
            WHERE c.client_id IS NULL
              AND c.account_number IS NOT NULL AND TRIM(c.account_number) <> ''
              AND TRIM(cl.account_number) = TRIM(c.account_number)
            """
        )
        print(f"Linked by account_number: {cur.rowcount}")

    # Fallback: for any still NULL client_id, fill display name from LMS mapping by reserve_number
    cur.execute(
        """
        SELECT reserve_number FROM charters WHERE client_id IS NULL AND reserve_number IS NOT NULL
        """
    )
    remaining = [r[0] for r in cur.fetchall()]
    print(f"Still NULL after link: {len(remaining)}")

    if remaining:
        lms_map, _ = build_combined_lms_mapping()
        to_fill = [(lms_map.get(str(r).zfill(6), ''), str(r).zfill(6)) for r in remaining]
        to_fill = [(name, rn) for name, rn in to_fill if name]
        print(f"Have LMS names for fallback display: {len(to_fill)}")

        if write and to_fill:
            cur.executemany(
                """
                UPDATE charters
                SET client_display_name = %s
                WHERE client_id IS NULL AND reserve_number = %s
                """,
                to_fill,
            )
            print(f"Backfilled display names from LMS: {cur.rowcount}")

    if write:
        conn.commit()
    else:
        conn.rollback()
        print("DRY-RUN only. No changes committed.")

    cur.close()
    conn.close()


if __name__ == '__main__':
    write = '--write' in sys.argv
    main(write=write)
