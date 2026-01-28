#!/usr/bin/env python3
"""
Recompute charters.payment_status based on linked payments coverage.
Sets to 'Reconciled' when total linked payments >= amount due within tolerance.
Writes a short summary to stdout.
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

TOL = float(os.getenv('RECON_TOLERANCE', '1.00'))


def main():
    load_dotenv('l:/limo/.env'); load_dotenv()
    conn = psycopg2.connect(
        dbname=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REMOVED***'),
        host=os.getenv('DB_HOST','localhost'),
        port=int(os.getenv('DB_PORT','5432')),
    )
    updated = 0
    total = 0
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                WITH paid AS (
                  SELECT c.charter_id,
                         COALESCE(c.total_amount_due, COALESCE(c.rate,0)) AS due,
                         COALESCE(SUM(p.amount),0) AS total_paid
                    FROM charters c
               LEFT JOIN payments p ON p.charter_id = c.charter_id
                   GROUP BY c.charter_id
                )
                UPDATE charters c
                   SET payment_status='Reconciled'
                  FROM paid
                 WHERE paid.charter_id = c.charter_id
                   AND (paid.total_paid + %s) >= paid.due
                   AND COALESCE(c.payment_status,'') <> 'Reconciled'
                """,
                (TOL,)
            )
            updated = cur.rowcount or 0
            cur.execute("SELECT COUNT(*) AS c FROM charters")
            total = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) AS c FROM charters WHERE payment_status IS DISTINCT FROM 'Reconciled'")
            remaining = cur.fetchone()['c']
    print(f"Payment status updated to Reconciled for {updated} charters (of {total}). Remaining not reconciled: {remaining}.")


if __name__ == '__main__':
    main()
