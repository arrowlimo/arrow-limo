import os
import sys
import argparse
import psycopg2


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reserves', required=True, help='Comma-separated list of reserve_numbers')
    args = ap.parse_args()

    reserves = [r.strip() for r in args.reserves.split(',') if r.strip()]
    if not reserves:
        print('No reserves provided')
        sys.exit(2)

    conn = connect(); cur = conn.cursor()

    print('Checking charters...')
    cur.execute(
        """
        SELECT reserve_number::text
        FROM charters
        WHERE reserve_number::text = ANY(%s)
        ORDER BY 1
        """,
        (reserves,)
    )
    rows = cur.fetchall()
    print('charters matches:', [r[0] for r in rows])

    # payments
    # Accept both amount columns; just existence check on reserve
    print('Checking payments...')
    cur.execute(
        """
        SELECT DISTINCT reserve_number::text
        FROM payments
        WHERE reserve_number::text = ANY(%s)
        ORDER BY 1
        """,
        (reserves,)
    )
    rows = cur.fetchall()
    print('payments matches:', [r[0] for r in rows])

    # charter_charges may or may not have reserve_number; check schema first
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema='public' AND table_name='charter_charges' AND column_name='reserve_number'
        """
    )
    has_reserve = cur.fetchone()[0] > 0
    if has_reserve:
        print('Checking charter_charges...')
        cur.execute(
            """
            SELECT DISTINCT reserve_number::text
            FROM charter_charges
            WHERE reserve_number::text = ANY(%s)
            ORDER BY 1
            """,
            (reserves,)
        )
        rows = cur.fetchall()
        print('charter_charges matches:', [r[0] for r in rows])
    else:
        print('charter_charges has no reserve_number column; skipping')

    cur.close(); conn.close()


if __name__ == '__main__':
    main()
