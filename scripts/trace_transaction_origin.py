import os
import psycopg2
import psycopg2.extras


def get_conn():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        dbname=os.environ.get("DB_NAME", "almsdata"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    )


def main():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    print("Connected.")

    # Get details on these specific transactions
    print("\n=== Transaction 80392, 80393 details ===")
    cur.execute(
        """
        select transaction_id, account_number, bank_id, transaction_date, 
               description, debit_amount, credit_amount, balance, 
               source_file, import_batch, category, vendor_extracted,
               created_at, updated_at
        from banking_transactions
        where transaction_id in (80392, 80393)
        order by transaction_id
        """
    )
    for r in cur.fetchall():
        print(f"\nTransaction ID: {r['transaction_id']}")
        print(f"  Date: {r['transaction_date']}")
        print(f"  Description: {r['description']}")
        print(f"  Account: {r['account_number']}, Bank_id: {r['bank_id']}")
        print(f"  Debit: {r['debit_amount']}, Credit: {r['credit_amount']}")
        print(f"  Balance: {r['balance']}")
        print(f"  Source: {r['source_file']}")
        print(f"  Import batch: {r['import_batch']}")
        print(f"  Category: {r['category']}")
        print(f"  Vendor: {r['vendor_extracted']}")
        print(f"  Created: {r['created_at']}")
        print(f"  Updated: {r['updated_at']}")

    # Check GL tables for these GL IDs
    print("\n=== Checking gl_transactions for GL IDs 1663, 83331 ===")
    cur.execute(
        """
        select table_name
        from information_schema.tables
        where table_schema='public' 
          and table_name ilike '%gl%transaction%'
        order by table_name
        """
    )
    gl_tables = [r[0] for r in cur.fetchall()]
    print(f"GL transaction tables: {gl_tables}")

    for tbl in gl_tables[:3]:  # Check first few
        try:
            cur.execute(f"select column_name from information_schema.columns where table_name=%s order by ordinal_position", (tbl,))
            cols = [r[0] for r in cur.fetchall()]
            print(f"\n{tbl} columns: {', '.join(cols[:10])}")
            
            # Try to find by transaction_id or gl_id
            if 'transaction_id' in cols or 'gl_transaction_id' in cols or 'entry_id' in cols:
                id_col = 'transaction_id' if 'transaction_id' in cols else ('gl_transaction_id' if 'gl_transaction_id' in cols else 'entry_id')
                cur.execute(f"select * from {tbl} where {id_col} in (1663, 83331) limit 5")
                rows = cur.fetchall()
                if rows:
                    print(f"  Found {len(rows)} rows:")
                    for r in rows:
                        print(f"    {dict(r)}")
        except Exception as e:
            print(f"  Error querying {tbl}: {e}")

    # Check all transactions with source_file containing 'general_ledger:1000'
    print("\n=== Count of transactions by source_file pattern ===")
    cur.execute(
        """
        select source_file, count(*) as cnt
        from banking_transactions
        where source_file ilike '%general_ledger%1000%'
          or source_file ilike '%GL ID%'
        group by source_file
        order by cnt desc
        limit 20
        """
    )
    for r in cur.fetchall():
        print(f"  {r['source_file']}: {r['cnt']}")

    # Check account 1000 references
    print("\n=== Checking for account 1000 in various tables ===")
    cur.execute(
        """
        select account_number, account_name, account_type
        from chart_of_accounts
        where account_number ilike '%1000%'
        limit 10
        """
    )
    rows = cur.fetchall()
    if rows:
        print("chart_of_accounts:")
        for r in rows:
            print(f"  {r['account_number']}: {r['account_name']} ({r['account_type']})")

    conn.close()


if __name__ == "__main__":
    main()
