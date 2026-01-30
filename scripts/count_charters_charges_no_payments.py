"""
Count charters with charges but no payments.
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
    ccols = columns(cur, 'charter_charges')
    
    amount_col = 'amount' if 'amount' in pcols else ('payment_amount' if 'payment_amount' in pcols else None)
    if not amount_col:
        print('Required columns not found.')
        return

    # Charters with charges but no payments
    cur.execute(
        f"""
        WITH charge_sums AS (
          SELECT charter_id, reserve_number, ROUND(SUM(COALESCE(amount,0))::numeric,2) AS charges_sum
          FROM charter_charges
          GROUP BY charter_id, reserve_number
        ),
        payment_sums AS (
          SELECT reserve_number, ROUND(SUM(COALESCE({amount_col},0))::numeric,2) AS paid
          FROM payments
          WHERE reserve_number IS NOT NULL
          GROUP BY reserve_number
        )
        SELECT c.reserve_number,
               CAST(c.charter_date AS DATE) AS charter_date,
               ROUND(COALESCE(c.total_amount_due,0)::numeric,2) AS total_due,
               COALESCE(cs.charges_sum,0) AS charges_sum,
               COALESCE(ps.paid,0) AS paid_sum,
               ROUND(COALESCE(c.balance,0)::numeric,2) AS balance
        FROM charters c
        LEFT JOIN charge_sums cs ON c.charter_id = cs.charter_id
        LEFT JOIN payment_sums ps ON c.reserve_number = ps.reserve_number
        WHERE COALESCE(cs.charges_sum,0) > 0
          AND COALESCE(ps.paid,0) = 0
        ORDER BY c.charter_date DESC
        """
    )
    results = cur.fetchall()

    print(f"Charters with charges but no payments: {len(results)}\n")
    
    if results:
        # Summary stats
        total_charges = sum(r[3] for r in results)
        total_balance = sum(r[5] for r in results)
        
        print(f"Total charges: ${total_charges:,.2f}")
        print(f"Total balance: ${total_balance:,.2f}\n")
        
        # Show first 20
        print("First 20 charters:")
        print("reserve_number | charter_date | total_due | charges_sum | paid_sum | balance")
        for rn, cdate, td, cs, ps, bal in results[:20]:
            print(f"{rn} | {cdate} | {td} | {cs} | {ps} | {bal}")
        
        if len(results) > 20:
            print(f"\n... and {len(results)-20} more")

    cur.close(); conn.close()


if __name__ == '__main__':
    main()
