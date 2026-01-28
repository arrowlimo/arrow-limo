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
        # Backup first
        print(f"Creating backup table banking_transactions_misclass_backup_{ts} ...")
        cur.execute(
            f"CREATE TABLE banking_transactions_misclass_backup_{ts} AS SELECT * FROM banking_transactions WHERE source_file ILIKE '%general_ledger%1000%1615%'"
        )
        print(f" - Backed up {cur.rowcount} rows")

        # Count affected rows
        cur.execute(
            """
            SELECT COUNT(*) 
            FROM banking_transactions 
            WHERE source_file ILIKE '%general_ledger%1000%1615%'
            """
        )
        count = cur.fetchone()[0]
        print(f"\nMoving {count} transactions from 1615 to 0228362...")

        # Update account_number and bank_id
        cur.execute(
            """
            UPDATE banking_transactions
            SET account_number = '0228362',
                bank_id = 1,
                updated_at = now()
            WHERE source_file ILIKE '%general_ledger%1000%1615%'
            """
        )
        updated = cur.rowcount
        print(f" - Updated {updated} rows")

        # Verify the changes
        print("\nVerifying changes...")
        cur.execute(
            """
            SELECT COUNT(*) 
            FROM banking_transactions 
            WHERE account_number = '0228362' AND bank_id = 1
              AND source_file ILIKE '%general_ledger%1000%'
            """
        )
        verify_count = cur.fetchone()[0]
        print(f" - {verify_count} rows now in 0228362 with bank_id=1 from GL 1000")

        # Check remaining 1615 count
        cur.execute(
            """
            SELECT COUNT(*) 
            FROM banking_transactions 
            WHERE account_number = '1615' OR bank_id = 4
            """
        )
        remaining = cur.fetchone()[0]
        print(f" - {remaining} rows remaining in 1615/bank_id=4")

        conn.commit()
        print("\nCommitted successfully.")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        print("Rolled back changes.")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
