import os
import sys
from datetime import datetime

import psycopg2
import psycopg2.extras


def get_conn():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        dbname=os.environ.get("DB_NAME", "almsdata"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "***REMOVED***"),
    )


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    print("Connected.")

    try:
        # 1) Backup alias table
        print("Backing up account_number_aliases ...")
        cur.execute(
            f"create table if not exists account_number_aliases_backup_{ts} as select * from account_number_aliases"
        )
        print(" - backup created: account_number_aliases_backup_" + ts)

        # 2) Normalize 1615-related aliases to canonical '74-61615'
        print("Updating 1615-related aliases to canonical '74-61615' ...")
        cur.execute(
            """
            update account_number_aliases
               set canonical_account_number = '74-61615'
             where statement_format in ('00339-7461615','7461615','74-61615','61615','1615')
            """
        )
        print(f" - rows updated: {cur.rowcount}")

        # 3) Remove overly broad branch-only alias (00339 -> 0228362)
        print("Removing branch-only alias '00339' to avoid conflation ...")
        cur.execute(
            """
            delete from account_number_aliases
             where statement_format = '00339' and canonical_account_number = '0228362'
            """
        )
        print(f" - rows deleted: {cur.rowcount}")

        # 4) Ensure bank_accounts entry for 74-61615
        print("Ensuring bank_accounts entry for 74-61615 ...")
        cur.execute(
            """
            select bank_id from bank_accounts where account_number = '74-61615'
            """
        )
        row = cur.fetchone()
        new_bank_id = None
        if row:
            new_bank_id = row[0]
            print(f" - existing bank_id: {new_bank_id}")
        else:
            cur.execute(
                """
                insert into bank_accounts (account_name, institution_name, account_number, account_type, currency, is_active, created_at)
                values ('CIBC Business Checking (Legacy 74-61615)', 'CIBC', '74-61615', 'checking', 'CAD', true, now())
                returning bank_id
                """
            )
            new_bank_id = cur.fetchone()[0]
            print(f" - created bank_id: {new_bank_id}")

        # 5) Backfill bank_id for 2012 rows with account_number in ('1615','74-61615')
        print("Counting target 2012 rows for bank_id backfill ...")
        cur.execute(
            """
            select count(*)
              from banking_transactions
             where transaction_date >= date '2012-01-01' and transaction_date < date '2013-01-01'
               and account_number in ('1615','74-61615')
               and (bank_id is null or bank_id <> %s)
            """,
            (new_bank_id,),
        )
        needed = cur.fetchone()[0]
        print(f" - rows needing update: {needed}")
        if needed:
            print("Updating bank_id for 2012 rows (1615/74-61615) ...")
            cur.execute(
                """
                update banking_transactions
                   set bank_id = %s
                 where transaction_date >= date '2012-01-01' and transaction_date < date '2013-01-01'
                   and account_number in ('1615','74-61615')
                   and (bank_id is null or bank_id <> %s)
                """,
                (new_bank_id, new_bank_id),
            )
            print(f" - rows updated: {cur.rowcount}")
        else:
            print(" - no updates required")

        conn.commit()
        print("Committed.")
    except Exception as e:
        conn.rollback()
        print("ERROR, rolled back:", e)
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
