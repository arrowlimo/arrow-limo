import os
import sys
import psycopg2
import psycopg2.extras


BACKUP_TABLE = "banking_transactions_bankid_backup_20251216_150244"


def get_conn():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        dbname=os.environ.get("DB_NAME", "almsdata"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "***REMOVED***"),
    )


def main():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    print("Connected.")

    # Verify backup table exists
    cur.execute(
        """
        select 1
        from information_schema.tables
        where table_schema='public' and table_name=%s
        """,
        (BACKUP_TABLE,),
    )
    if cur.fetchone() is None:
        print(f"Backup table {BACKUP_TABLE} not found. Aborting.")
        sys.exit(1)

    print("Restoring balances from backup table ...")
    cur.execute(
        f"""
        with src as (
            select transaction_id, balance as backup_balance
            from {BACKUP_TABLE}
        )
        update banking_transactions bt
           set balance = src.backup_balance
          from src
         where bt.transaction_id = src.transaction_id
        """
    )
    print(f" - rows updated: {cur.rowcount}")

    conn.commit()
    print("Committed.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
