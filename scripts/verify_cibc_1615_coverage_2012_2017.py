import os
import psycopg2
import psycopg2.extras


def get_conn():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        dbname=os.environ.get("DB_NAME", "almsdata"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "***REMOVED***"),
    )


YEARS = [2012, 2013, 2014, 2015, 2016, 2017]


def main():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    print("Connected.")

    # Resolve bank_id for 74-61615 if present
    cur.execute("select bank_id from bank_accounts where account_number='74-61615'")
    row = cur.fetchone()
    bank4 = row[0] if row else None
    print(f"74-61615 bank_id: {bank4}")

    for y in YEARS:
        y1 = f"{y}-01-01"
        y2 = f"{y+1}-01-01"
        print(f"\nYear {y}")
        # Counts by account_number for 1615 family
        cur.execute(
            """
            select account_number,
                   count(*) as cnt,
                   min(transaction_date) as min_dt,
                   max(transaction_date) as max_dt
            from banking_transactions
            where transaction_date >= %s and transaction_date < %s
              and account_number in ('1615','74-61615')
            group by account_number
            order by cnt desc
            """,
            (y1, y2),
        )
        rows = cur.fetchall()
        if rows:
            for r in rows:
                print(f" - acct={r['account_number']}: cnt={r['cnt']} range=[{r['min_dt']},{r['max_dt']}]")
        else:
            print(" - no rows for 1615/74-61615 by account_number")

        # By bank_id (if exists)
        if bank4 is not None:
            cur.execute(
                """
                select count(*) as cnt,
                       min(transaction_date) as min_dt,
                       max(transaction_date) as max_dt
                from banking_transactions
                where transaction_date >= %s and transaction_date < %s
                  and bank_id = %s
                """,
                (y1, y2, bank4),
            )
            r = cur.fetchone()
            print(f" - bank_id={bank4}: cnt={r['cnt']} range=[{r['min_dt']},{r['max_dt']}]")

        # Monthly breakdown (account_number family)
        cur.execute(
            """
            select to_char(transaction_date, 'YYYY-MM') as ym, count(*) as cnt
            from banking_transactions
            where transaction_date >= %s and transaction_date < %s
              and account_number in ('1615','74-61615')
            group by 1
            order by 1
            """,
            (y1, y2),
        )
        months = cur.fetchall()
        if months:
            print(" - months:")
            for m in months:
                print(f"   * {m['ym']}: {m['cnt']}")
        else:
            print(" - no monthly rows")

    conn.close()


if __name__ == "__main__":
    main()
