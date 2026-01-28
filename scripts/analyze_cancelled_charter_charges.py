import os
import psycopg2


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    )


def main():
    conn = connect(); cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM charters WHERE COALESCE(cancelled, FALSE) = TRUE")
    total_cancelled = cur.fetchone()[0]

    # Cancelled with any charter_charges rows
    cur.execute(
        """
        SELECT COUNT(DISTINCT c.reserve_number)
        FROM charters c
        JOIN charter_charges ch ON ch.reserve_number::text = c.reserve_number::text
        WHERE COALESCE(c.cancelled, FALSE) = TRUE
        """
    )
    cancelled_with_any_charge_rows = cur.fetchone()[0]

    # Cancelled with positive charge sums
    cur.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT c.reserve_number, COALESCE(SUM(ch.amount),0) AS charges_sum
            FROM charters c
            LEFT JOIN charter_charges ch ON ch.reserve_number::text = c.reserve_number::text
            WHERE COALESCE(c.cancelled, FALSE) = TRUE
            GROUP BY c.reserve_number
        ) t
        WHERE t.charges_sum > 0
        """
    )
    cancelled_with_positive_charges = cur.fetchone()[0]

    # Totals: total_amount_due vs sum(charges) for cancelled only
    cur.execute(
        """
        WITH sums AS (
            SELECT c.reserve_number,
                   ROUND(COALESCE(SUM(ch.amount),0)::numeric,2) AS charges_sum
            FROM charters c
            LEFT JOIN charter_charges ch ON ch.reserve_number::text = c.reserve_number::text
            WHERE COALESCE(c.cancelled, FALSE) = TRUE
            GROUP BY c.reserve_number
        )
        SELECT ROUND(COALESCE(SUM(c.total_amount_due),0)::numeric,2) AS total_due_sum,
               ROUND(COALESCE(SUM(s.charges_sum),0)::numeric,2) AS charges_sum_total
        FROM charters c
        JOIN sums s ON s.reserve_number = c.reserve_number
        WHERE COALESCE(c.cancelled, FALSE) = TRUE
        """
    )
    total_due_sum, charges_sum_total = cur.fetchone()

    # Sample cancelled charters with non-zero charges or non-zero total_due
    cur.execute(
        """
        WITH sums AS (
            SELECT c.reserve_number,
                   ROUND(COALESCE(SUM(ch.amount),0)::numeric,2) AS charges_sum
            FROM charters c
            LEFT JOIN charter_charges ch ON ch.reserve_number::text = c.reserve_number::text
            WHERE COALESCE(c.cancelled, FALSE) = TRUE
            GROUP BY c.reserve_number
        )
        SELECT c.reserve_number::text, CAST(c.charter_date AS DATE), c.total_amount_due, s.charges_sum, c.paid_amount, c.balance
        FROM charters c
        JOIN sums s ON s.reserve_number = c.reserve_number
        WHERE COALESCE(c.cancelled, FALSE) = TRUE
          AND (s.charges_sum <> 0 OR COALESCE(c.total_amount_due,0) <> 0)
        ORDER BY c.reserve_number
        LIMIT 25
        """
    )
    samples = cur.fetchall()

    print(f"Total cancelled charters: {total_cancelled}")
    print(f"Cancelled with any charge rows: {cancelled_with_any_charge_rows}")
    print(f"Cancelled with positive charges: {cancelled_with_positive_charges}")
    print(f"Cancelled totals - total_amount_due sum: {total_due_sum}, charges sum total: {charges_sum_total}")
    if samples:
        print("\nSample cancelled with non-zero charges or total_due:")
        for row in samples:
            rn, cdate, total_due, charges_sum, paid, bal = row
            print(f"{rn} | {cdate} | total_due={total_due} | charges={charges_sum} | paid={paid} | balance={bal}")
    else:
        print("\nAll cancelled charters have zero charges and zero total_due in sample window.")

    cur.close(); conn.close()


if __name__ == '__main__':
    main()