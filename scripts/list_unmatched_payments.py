"""
List details of the 3 remaining unmatched payments.
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
        print('Required columns not found.')
        return

    # Unmatched payments
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
    unmatched = cur.fetchall()

    print(f"Unmatched payments: {len(unmatched)}\n")
    if unmatched:
        print("payment_id | reserve_number | amount | date | method | key")
        for pid, rn, amt, pdate, method, pkey in unmatched:
            print(f"{pid} | {rn} | {amt} | {pdate} | {method} | {pkey}")

    cur.close(); conn.close()


if __name__ == '__main__':
    main()
