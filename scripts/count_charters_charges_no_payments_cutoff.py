"""
Count charters with charges but zero payments, before a cutoff date.
Default cutoff: 2025-10-01 (prior to Oct 2025).
"""
import os
import argparse
from datetime import datetime
import psycopg2


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cutoff', default='2025-10-01', help='YYYY-MM-DD; include charters strictly before this date')
    args = ap.parse_args()

    # Validate date
    try:
        cutoff_date = datetime.strptime(args.cutoff, '%Y-%m-%d').date()
    except ValueError:
        print('Invalid --cutoff; expected YYYY-MM-DD')
        return

    conn = connect(); cur = conn.cursor()

    pcols = columns(cur, 'payments')
    amount_col = 'amount' if 'amount' in pcols else ('payment_amount' if 'payment_amount' in pcols else None)
    if not amount_col:
        print('payments amount column not found')
        return

    # Use reserve_number as business key for both charges and payments; filter by charter_date < cutoff
    cur.execute(
        f"""
        WITH charge_sums AS (
          SELECT reserve_number::text AS reserve_text,
                 ROUND(SUM(COALESCE(amount,0))::numeric,2) AS charges_sum
          FROM charter_charges
          GROUP BY reserve_text
        ),
        payment_sums AS (
          SELECT reserve_number::text AS reserve_text,
                 ROUND(SUM(COALESCE({amount_col},0))::numeric,2) AS paid
          FROM payments
          WHERE reserve_number IS NOT NULL
          GROUP BY reserve_text
        )
        SELECT c.reserve_number,
               CAST(c.charter_date AS DATE) AS charter_date,
               ROUND(COALESCE(c.total_amount_due,0)::numeric,2) AS total_due,
               COALESCE(cs.charges_sum,0) AS charges_sum,
               COALESCE(ps.paid,0) AS paid_sum,
               ROUND(COALESCE(c.balance,0)::numeric,2) AS balance
        FROM charters c
        LEFT JOIN charge_sums cs ON cs.reserve_text = c.reserve_number::text
        LEFT JOIN payment_sums ps ON ps.reserve_text = c.reserve_number::text
        WHERE CAST(c.charter_date AS DATE) < %s
          AND COALESCE(cs.charges_sum,0) > 0
          AND COALESCE(ps.paid,0) = 0
        ORDER BY c.charter_date DESC
        """,
        (cutoff_date,)
    )
    rows = cur.fetchall()

    count = len(rows)
    total_charges = sum(r[3] for r in rows)
    total_balance = sum(r[5] for r in rows)

    print(f"Cutoff (exclusive): {cutoff_date}")
    print(f"Charters with charges but zero payments before cutoff: {count}")
    print(f"Total charges: ${total_charges:,.2f}")
    print(f"Total balance: ${total_balance:,.2f}")

    if rows:
        print("\nFirst 20:")
        print("reserve_number | charter_date | total_due | charges_sum | paid_sum | balance")
        for rn, cdate, td, cs, ps, bal in rows[:20]:
            print(f"{rn} | {cdate} | {td} | {cs} | {ps} | {bal}")
        if len(rows) > 20:
            print(f"\n... and {len(rows)-20} more")

    cur.close(); conn.close()


if __name__ == '__main__':
    main()