"""
List details of duplicate payment groups flagged by integrity check.

Definition matches verify_almsdata_integrity.py:
Duplicates = same (reserve_number, amount, date-only of payment_date/created_at/...)

Prints each duplicate group key and the rows within it.
"""
import os
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
    conn = connect(); cur = conn.cursor()
    pcols = columns(cur, 'payments')
    amount_col = 'amount' if 'amount' in pcols else ('payment_amount' if 'payment_amount' in pcols else None)
    date_col = None
    for cand in ('payment_date', 'created_at', 'last_updated', 'updated_at'):
        if cand in pcols:
            date_col = cand
            break
    if not amount_col or not date_col:
        print('Required columns not found on payments.')
        return

    # Find duplicate groups (same reserve_number, amount, date-only)
    cur.execute(
        f"""
        SELECT reserve_number, {amount_col} AS amount, CAST({date_col} AS DATE) AS d, COUNT(*) AS n
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number, {amount_col}, CAST({date_col} AS DATE)
        HAVING COUNT(*) > 1
        ORDER BY d, reserve_number, amount
        """
    )
    groups = cur.fetchall()
    if not groups:
        print('No duplicate groups found.')
        return

    print(f"Duplicate groups found: {len(groups)}\n")

    for rn, amount, d, n in groups:
        print(f"== Group: reserve_number={rn}, amount={amount}, date={d} (rows={n})")
        cur.execute(
            f"""
            SELECT payment_id, reserve_number, {amount_col} AS amount,
                   CAST({date_col} AS DATE) AS pdate,
                   COALESCE(payment_method,'') AS payment_method,
                   COALESCE(payment_key,'') AS payment_key
            FROM payments
            WHERE reserve_number = %s
              AND COALESCE({amount_col},0) = COALESCE(%s,0)
              AND CAST({date_col} AS DATE) = %s
            ORDER BY payment_id
            """,
            (rn, amount, d)
        )
        rows = cur.fetchall()
        for r in rows:
            pid, rn2, amt2, pdate, method, key = r
            print(f"  - payment_id={pid} reserve_number={rn2} amount={amt2} date={pdate} method={method} key={key}")
        print()

    cur.close(); conn.close()


if __name__ == '__main__':
    main()
