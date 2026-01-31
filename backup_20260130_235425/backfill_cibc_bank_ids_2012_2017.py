import os
import sys
from datetime import datetime

import psycopg2
import psycopg2.extras


YEARS = [2012, 2013, 2014, 2015, 2016, 2017]


def get_conn():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        dbname=os.environ.get("DB_NAME", "almsdata"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    )


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    print("Connected.")

    try:
        # Resolve bank_ids, ensure both exist
        cur.execute("select bank_id from bank_accounts where account_number='0228362'")
        row = cur.fetchone()
        bank_0228362 = row[0] if row else None
        if bank_0228362 is None:
            cur.execute(
                """
                insert into bank_accounts (account_name, institution_name, account_number, account_type, currency, is_active, created_at)
                values ('CIBC Business Checking', 'CIBC', '0228362', 'checking', 'CAD', true, now())
                returning bank_id
                """
            )
            bank_0228362 = cur.fetchone()[0]
        print(f"bank_id for 0228362: {bank_0228362}")

        cur.execute("select bank_id from bank_accounts where account_number='74-61615'")
        row = cur.fetchone()
        bank_7461615 = row[0] if row else None
        if bank_7461615 is None:
            cur.execute(
                """
                insert into bank_accounts (account_name, institution_name, account_number, account_type, currency, is_active, created_at)
                values ('CIBC Business Checking (Legacy 74-61615)', 'CIBC', '74-61615', 'checking', 'CAD', true, now())
                returning bank_id
                """
            )
            bank_7461615 = cur.fetchone()[0]
        print(f"bank_id for 74-61615: {bank_7461615}")

        # Backup main table before updates
        print("Creating backup table for banking_transactions ...")
        cur.execute(
            f"create table if not exists banking_transactions_bankid_backup_{ts} as select * from banking_transactions"
        )
        print(" - backup created: banking_transactions_bankid_backup_" + ts)

        total_updates = 0

        # Backfill across years
        for y in YEARS:
            y1 = f"{y}-01-01"
            y2 = f"{y+1}-01-01"
            print(f"\nYear {y}")
            # 1615 family → bank_7461615
            cur.execute(
                """
                select count(*) from banking_transactions
                 where transaction_date >= %s and transaction_date < %s
                   and account_number in ('1615','74-61615')
                   and (bank_id is null or bank_id <> %s)
                """,
                (y1, y2, bank_7461615),
            )
            c_need_1615 = cur.fetchone()[0]
            print(f" - 1615/74-61615 needing bank_id={bank_7461615}: {c_need_1615}")
            if c_need_1615:
                cur.execute(
                    """
                    update banking_transactions
                       set bank_id = %s
                     where transaction_date >= %s and transaction_date < %s
                       and account_number in ('1615','74-61615')
                       and (bank_id is null or bank_id <> %s)
                    """,
                    (bank_7461615, y1, y2, bank_7461615),
                )
                print(f"   * updated 1615/74-61615 rows: {cur.rowcount}")
                total_updates += cur.rowcount

            # 0228362 → bank_0228362
            cur.execute(
                """
                select count(*) from banking_transactions
                 where transaction_date >= %s and transaction_date < %s
                   and account_number = '0228362'
                   and (bank_id is null or bank_id <> %s)
                """,
                (y1, y2, bank_0228362),
            )
            c_need_8362 = cur.fetchone()[0]
            print(f" - 0228362 needing bank_id={bank_0228362}: {c_need_8362}")
            if c_need_8362:
                cur.execute(
                    """
                    update banking_transactions
                       set bank_id = %s
                     where transaction_date >= %s and transaction_date < %s
                       and account_number = '0228362'
                       and (bank_id is null or bank_id <> %s)
                    """,
                    (bank_0228362, y1, y2, bank_0228362),
                )
                print(f"   * updated 0228362 rows: {cur.rowcount}")
                total_updates += cur.rowcount

        conn.commit()
        print(f"\nCommitted. Total rows updated: {total_updates}")
    except Exception as e:
        conn.rollback()
        print("ERROR, rolled back:", e)
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
