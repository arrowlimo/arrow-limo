import os
import sys
from datetime import date, datetime

import psycopg2
import psycopg2.extras

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

SCOTIA_BANK_ID = 2
SCOTIA_ACCOUNT = "903990106011"


def get_conn():
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def main():
    write = '--write' in sys.argv
    conn = get_conn()
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    print("="*80)
    print("SCOTIA BANK DATA CLEANUP")
    print("="*80)
    
    try:
        # Backup first
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_table = f"banking_transactions_scotia_backup_{ts}"
        
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {backup_table} AS
            SELECT * FROM banking_transactions
            WHERE account_number = %s
        """, (SCOTIA_ACCOUNT,))
        
        print(f"\n✅ Backup created: {backup_table}")
        
        # Check current state
        cur.execute("""
            SELECT bank_id, COUNT(*) 
            FROM banking_transactions
            WHERE account_number = %s
            GROUP BY bank_id
        """, (SCOTIA_ACCOUNT,))
        
        print(f"\nCurrent bank_id distribution for {SCOTIA_ACCOUNT}:")
        for bid, cnt in cur.fetchall():
            print(f"  bank_id={bid}: {cnt:,}")
        
        # Update bank_id to 2 for all Scotia transactions
        cur.execute("""
            UPDATE banking_transactions
            SET bank_id = %s
            WHERE account_number = %s
              AND bank_id IS DISTINCT FROM %s
        """, (SCOTIA_BANK_ID, SCOTIA_ACCOUNT, SCOTIA_BANK_ID))
        
        updated = cur.rowcount
        print(f"\nUpdated {updated:,} transactions to bank_id={SCOTIA_BANK_ID}")
        
        # Update receipts mapped_bank_account_id
        cur.execute("""
            UPDATE receipts r
            SET mapped_bank_account_id = %s
            FROM banking_transactions bt
            WHERE bt.transaction_id = r.banking_transaction_id
              AND bt.account_number = %s
              AND r.mapped_bank_account_id IS DISTINCT FROM %s
        """, (SCOTIA_BANK_ID, SCOTIA_ACCOUNT, SCOTIA_BANK_ID))
        
        receipts_updated = cur.rowcount
        print(f"Updated {receipts_updated:,} receipts to mapped_bank_account_id={SCOTIA_BANK_ID}")
        
        if write:
            conn.commit()
            print("\n✅ Changes committed")
        else:
            conn.rollback()
            print("\n⚠️  DRY RUN - changes rolled back (use --write to commit)")
        
        # Final summary
        cur.execute("""
            SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date)
            FROM banking_transactions
            WHERE bank_id = %s AND account_number = %s
        """, (SCOTIA_BANK_ID, SCOTIA_ACCOUNT))
        
        count, min_date, max_date = cur.fetchone()
        print(f"\n{'Final' if write else 'Preview'} Scotia Bank stats:")
        print(f"  Total: {count:,} transactions")
        print(f"  Date range: {min_date} to {max_date}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
