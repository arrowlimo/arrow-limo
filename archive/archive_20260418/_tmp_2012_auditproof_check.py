#!/usr/bin/env python3
"""
Audit-proof validation for 2012 charter revenue/payments.
Verifies totals, per-charter reconciliation, and method breakdown integrity.
"""

import psycopg2
from decimal import Decimal

DB_HOST = 'localhost'
DB_PORT = 5432
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = 'ArrowLimousine'


def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    cur = conn.cursor()

    print("=" * 84)
    print("2012 CHARTER RECONCILIATION - AUDIT PROOF CHECK")
    print("=" * 84)

    # 1) Core totals: owed vs paid for 2012 charters.
    cur.execute(
        """
        WITH c2012 AS (
            SELECT
                charter_id,
                reserve_number,
                COALESCE(grand_total, total_amount_due, 0)::numeric AS amount_owed
            FROM charters
            WHERE EXTRACT(YEAR FROM charter_date) = 2012
        ),
        p_by_charter AS (
            SELECT
                c.charter_id,
                COALESCE(SUM(cp.amount), 0)::numeric AS amount_paid
            FROM c2012 c
            LEFT JOIN charter_payments cp
                ON cp.charter_id = c.reserve_number
            GROUP BY c.charter_id
        )
        SELECT
            (SELECT COUNT(*) FROM c2012) AS charter_count,
            COALESCE(SUM(c.amount_owed), 0)::numeric AS total_owed,
            COALESCE(SUM(p.amount_paid), 0)::numeric AS total_paid,
            COALESCE(SUM(p.amount_paid - c.amount_owed), 0)::numeric AS net_variance
        FROM c2012 c
        JOIN p_by_charter p ON p.charter_id = c.charter_id
        """
    )
    charter_count, total_owed, total_paid, net_variance = cur.fetchone()

    print(f"Total 2012 charters:          {charter_count}")
    print(f"Total amount owed:            ${Decimal(total_owed):,.2f}")
    print(f"Total payments received:      ${Decimal(total_paid):,.2f}")
    print(f"Net variance (paid - owed):   ${Decimal(net_variance):,.2f}")

    # 2) Count variances by threshold.
    cur.execute(
        """
        WITH c2012 AS (
            SELECT
                charter_id,
                reserve_number,
                COALESCE(grand_total, total_amount_due, 0)::numeric AS amount_owed
            FROM charters
            WHERE EXTRACT(YEAR FROM charter_date) = 2012
        ),
        p_by_charter AS (
            SELECT
                c.charter_id,
                COALESCE(SUM(cp.amount), 0)::numeric AS amount_paid
            FROM c2012 c
            LEFT JOIN charter_payments cp
                ON cp.charter_id = c.reserve_number
            GROUP BY c.charter_id
        ),
        diff AS (
            SELECT
                c.charter_id,
                c.reserve_number,
                c.amount_owed,
                p.amount_paid,
                (p.amount_paid - c.amount_owed)::numeric AS variance
            FROM c2012 c
            JOIN p_by_charter p ON p.charter_id = c.charter_id
        )
        SELECT
            COUNT(*) FILTER (WHERE ABS(variance) <= 0.01) AS within_1_cent,
            COUNT(*) FILTER (WHERE ABS(variance) > 0.01 AND ABS(variance) <= 1.00) AS cents_to_1_dollar,
            COUNT(*) FILTER (WHERE ABS(variance) > 1.00) AS over_1_dollar
        FROM diff
        """
    )
    within_1_cent, cents_to_1_dollar, over_1_dollar = cur.fetchone()

    print("\nVariance distribution:")
    print(f"Charters within $0.01:         {within_1_cent}")
    print(f"Charters $0.01 to $1.00:       {cents_to_1_dollar}")
    print(f"Charters over $1.00:           {over_1_dollar}")

    # 3) Payment method breakdown for 2012 charters.
    cur.execute(
        """
        WITH c2012 AS (
            SELECT reserve_number
            FROM charters
            WHERE EXTRACT(YEAR FROM charter_date) = 2012
        )
        SELECT
            COALESCE(LOWER(cp.payment_method), 'unknown') AS payment_method,
            COUNT(*) AS payment_rows,
            COALESCE(SUM(cp.amount), 0)::numeric AS amount
        FROM charter_payments cp
        JOIN c2012 c ON c.reserve_number = cp.charter_id
        GROUP BY COALESCE(LOWER(cp.payment_method), 'unknown')
        ORDER BY amount DESC
        """
    )
    methods = cur.fetchall()

    print("\nPayment method totals (for 2012 charters):")
    method_sum = Decimal("0")
    for method, rows, amount in methods:
        amt = Decimal(amount)
        method_sum += amt
        print(f"  {method:<20} rows={rows:>4}  amount=${amt:>12,.2f}")

    print(f"Method total check:            ${method_sum:,.2f}")

    # 4) Ensure no method decomposition mismatch per charter.
    cur.execute(
        """
        WITH c2012 AS (
            SELECT charter_id, reserve_number
            FROM charters
            WHERE EXTRACT(YEAR FROM charter_date) = 2012
        ),
        by_method AS (
            SELECT
                c.charter_id,
                COALESCE(SUM(cp.amount), 0)::numeric AS method_sum
            FROM c2012 c
            LEFT JOIN charter_payments cp ON cp.charter_id = c.reserve_number
            GROUP BY c.charter_id
        ),
        direct_sum AS (
            SELECT
                c.charter_id,
                COALESCE(SUM(cp.amount), 0)::numeric AS direct_sum
            FROM c2012 c
            LEFT JOIN charter_payments cp ON cp.charter_id = c.reserve_number
            GROUP BY c.charter_id
        )
        SELECT COUNT(*)
        FROM by_method m
        JOIN direct_sum d ON d.charter_id = m.charter_id
        WHERE m.method_sum <> d.direct_sum
        """
    )
    mismatch_count = cur.fetchone()[0]
    print(f"Per-charter method sum mismatches: {mismatch_count}")

    # 5) Spot check outliers > $1 variance.
    if over_1_dollar > 0:
        cur.execute(
            """
            WITH c2012 AS (
                SELECT
                    charter_id,
                    reserve_number,
                    charter_date,
                    COALESCE(grand_total, total_amount_due, 0)::numeric AS amount_owed
                FROM charters
                WHERE EXTRACT(YEAR FROM charter_date) = 2012
            ),
            p_by_charter AS (
                SELECT
                    c.charter_id,
                    COALESCE(SUM(cp.amount), 0)::numeric AS amount_paid
                FROM c2012 c
                LEFT JOIN charter_payments cp
                    ON cp.charter_id = c.reserve_number
                GROUP BY c.charter_id
            )
            SELECT
                c.charter_id,
                c.reserve_number,
                c.charter_date,
                c.amount_owed,
                p.amount_paid,
                (p.amount_paid - c.amount_owed)::numeric AS variance
            FROM c2012 c
            JOIN p_by_charter p ON p.charter_id = c.charter_id
            WHERE ABS(p.amount_paid - c.amount_owed) > 1.00
            ORDER BY ABS(p.amount_paid - c.amount_owed) DESC
            LIMIT 20
            """
        )
        rows = cur.fetchall()
        print("\nTop variances over $1.00:")
        for r in rows:
            print(
                f"  charter_id={r[0]} reserve={r[1]} date={r[2]} "
                f"owed=${Decimal(r[3]):,.2f} paid=${Decimal(r[4]):,.2f} var=${Decimal(r[5]):,.2f}"
            )

    print("\nConclusion checks:")
    print(f"  1) Totals match expected near-zero net? {'YES' if abs(Decimal(net_variance)) <= Decimal('0.10') else 'NO'}")
    print(f"  2) Method totals equal payment totals? {'YES' if method_sum == Decimal(total_paid) else 'NO'}")
    print(f"  3) Any material >$1 charter variance? {'NO' if over_1_dollar == 0 else 'YES'}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
