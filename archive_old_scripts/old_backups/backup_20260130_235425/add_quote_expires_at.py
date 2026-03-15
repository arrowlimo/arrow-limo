import os
import sys
import psycopg2
from psycopg2 import sql


def get_conn():
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_NAME = os.environ.get("DB_NAME", "almsdata")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def column_exists(cur, table, column):
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s AND column_name=%s
        """,
        (table, column),
    )
    return cur.fetchone() is not None


def main():
    dry_run = "--dry-run" in sys.argv
    conn = get_conn()
    cur = conn.cursor()
    try:
        # Verify target table exists
        cur.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema='public' AND table_name='charters'
            """
        )
        if cur.fetchone() is None:
            print("ERROR: Table 'charters' not found in schema 'public'. Aborting.")
            return 2

        added = False
        if not column_exists(cur, "charters", "quote_expires_at"):
            print("Adding column charters.quote_expires_at TIMESTAMP ...")
            if not dry_run:
                cur.execute("ALTER TABLE charters ADD COLUMN quote_expires_at TIMESTAMP NULL")
            added = True
        else:
            print("Column charters.quote_expires_at already exists. Skipping add.")

        # Post-populate for existing Quote records if created_at exists
        # Default: created_at + 7 days
        if column_exists(cur, "charters", "created_at"):
            print("Backfilling quote_expires_at for existing quotes where missing ...")
            if not dry_run:
                cur.execute(
                    """
                    UPDATE charters
                    SET quote_expires_at = created_at + INTERVAL '7 days'
                    WHERE status = 'Quote' AND quote_expires_at IS NULL AND created_at IS NOT NULL
                    """
                )
                print(f"Backfilled rows: {cur.rowcount}")
        else:
            print("WARNING: charters.created_at not found. Skipping backfill.")

        if dry_run:
            print("Dry-run complete. No changes committed.")
            conn.rollback()
        else:
            conn.commit()
            print("Committed changes successfully.")

        return 0
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        return 1
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
