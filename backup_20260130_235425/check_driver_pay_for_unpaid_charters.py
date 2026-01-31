"""
Check if charters with charges but zero payments (before cutoff) have driver payroll entries.

Default cutoff: 2025-10-01 (strictly before).
Outputs a console summary and lists first 25 matches.
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

    # Verify driver_payroll columns
    dpcols = columns(cur, 'driver_payroll')
    has_dp_reserve = 'reserve_number' in dpcols
    has_dp_charter_id = 'charter_id' in dpcols

    # Build unpaid charter set before cutoff (charges > 0, payments = 0)
    cur.execute(
        """
        WITH charge_sums AS (
          SELECT reserve_number::text AS reserve_text,
                 ROUND(SUM(COALESCE(amount,0))::numeric,2) AS charges_sum
          FROM charter_charges
          GROUP BY reserve_text
        ),
        payment_sums AS (
          SELECT reserve_number::text AS reserve_text,
                 ROUND(SUM(COALESCE(amount,0))::numeric,2) AS paid
          FROM payments
          WHERE reserve_number IS NOT NULL
          GROUP BY reserve_text
        ),
        unpaid AS (
          SELECT c.charter_id,
                 c.reserve_number::text AS reserve_text,
                 CAST(c.charter_date AS DATE) AS charter_date,
                 COALESCE(cs.charges_sum,0) AS charges_sum,
                 COALESCE(ps.paid,0) AS paid_sum
          FROM charters c
          LEFT JOIN charge_sums cs ON cs.reserve_text = c.reserve_number::text
          LEFT JOIN payment_sums ps ON ps.reserve_text = c.reserve_number::text
          WHERE CAST(c.charter_date AS DATE) < %s
            AND COALESCE(cs.charges_sum,0) > 0
            AND COALESCE(ps.paid,0) = 0
        )
        SELECT charter_id, reserve_text, charter_date, charges_sum
        FROM unpaid
        ORDER BY charter_date DESC
        """,
        (cutoff_date,)
    )
    unpaid_rows = cur.fetchall()
    unpaid_ids = [r[0] for r in unpaid_rows if r[0] is not None]
    unpaid_ids_text = [str(i) for i in unpaid_ids]
    unpaid_reserves = [r[1] for r in unpaid_rows]

    if not unpaid_rows:
        print(f"No unpaid-with-charges charters before {cutoff_date}.")
        cur.close(); conn.close(); return

    # Find driver_payroll matches
    matches = []
    total_matches = 0

    if has_dp_reserve:
        cur.execute(
            """
            SELECT dp.id, dp.reserve_number::text, dp.charter_id, dp.driver_id, dp.pay_date, dp.gross_pay
            FROM driver_payroll dp
            WHERE dp.reserve_number::text = ANY(%s)
            ORDER BY dp.pay_date DESC NULLS LAST
            LIMIT 100
            """,
            (unpaid_reserves,)
        )
        matches.extend(cur.fetchall())
        total_matches += len(matches)

    if has_dp_charter_id and unpaid_ids_text:
        cur.execute(
            """
            SELECT dp.id, dp.reserve_number::text, dp.charter_id, dp.driver_id, dp.pay_date, dp.gross_pay
            FROM driver_payroll dp
            WHERE dp.charter_id::text = ANY(%s)
            ORDER BY dp.pay_date DESC NULLS LAST
            LIMIT 100
            """,
            (unpaid_ids_text,)
        )
        id_matches = cur.fetchall()
        # Avoid duplicate rows if both conditions matched
        seen = {(m[0],) for m in matches}
        for row in id_matches:
            if (row[0],) not in seen:
                matches.append(row)
        total_matches = len(matches)

    # Summary
    print(f"Cutoff (exclusive): {cutoff_date}")
    print(f"Unpaid-with-charges charters: {len(unpaid_rows)}")
    print(f"Driver payroll matches among them: {total_matches}")

    if matches:
        print("\nSample matches (up to 25):")
        print("dp_id | reserve_number | charter_id | driver_id | pay_date | gross_pay")
        for row in matches[:25]:
            dp_id, rn, ch_id, drv_id, pay_date, gross = row
            print(f"{dp_id} | {rn} | {ch_id} | {drv_id} | {pay_date} | {gross}")

    cur.close(); conn.close()


if __name__ == '__main__':
    main()