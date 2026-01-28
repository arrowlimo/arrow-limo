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


def main():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    print("Connected.")

    # Find specific transactions
    print("\n=== Looking for transaction IDs 80392, 80393 ===")
    cur.execute(
        """
        select transaction_id, account_number, bank_id, transaction_date, 
               description, debit_amount, credit_amount, balance, source_file
        from banking_transactions
        where transaction_id in (80392, 80393)
        order by transaction_id
        """
    )
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"\nID: {r['transaction_id']}")
            print(f"  Date: {r['transaction_date']}")
            print(f"  Account: {r['account_number']}")
            print(f"  Bank_id: {r['bank_id']}")
            print(f"  Description: {r['description']}")
            print(f"  Debit: {r['debit_amount']}, Credit: {r['credit_amount']}")
            print(f"  Balance: {r['balance']}")
            print(f"  Source: {r['source_file']}")
    else:
        print("No rows found for these transaction_ids")

    # Check for transactions with account_number containing 1615 but bank_id != 4
    print("\n=== Checking for 1615-related transactions with wrong or NULL bank_id ===")
    cur.execute(
        """
        select count(*) as cnt,
               bank_id,
               account_number
        from banking_transactions
        where (account_number ilike '%1615%' or account_number ilike '%7461615%')
          and transaction_date >= date '2012-01-01'
        group by bank_id, account_number
        order by cnt desc
        """
    )
    rows = cur.fetchall()
    for r in rows:
        print(f"  Account: {r['account_number']}, bank_id: {r['bank_id']}, count: {r['cnt']}")

    # Check for transactions with bank_id=4 but account_number NOT matching 1615 pattern
    print("\n=== Checking for bank_id=4 with unexpected account_number ===")
    cur.execute(
        """
        select account_number, count(*) as cnt
        from banking_transactions
        where bank_id = 4
          and account_number not in ('1615', '74-61615')
        group by account_number
        order by cnt desc
        """
    )
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"  Account: {r['account_number']}, count: {r['cnt']}")
    else:
        print("  None found - all bank_id=4 have correct account_number")

    # Sample some transactions around the date 01-11-2012 for bank_id=4
    print("\n=== Sample transactions around 2012-01-11 for bank_id=4 ===")
    cur.execute(
        """
        select transaction_id, transaction_date, description, 
               debit_amount, credit_amount, account_number, source_file
        from banking_transactions
        where bank_id = 4
          and transaction_date between date '2012-01-10' and date '2012-01-12'
        order by transaction_date, transaction_id
        limit 20
        """
    )
    rows = cur.fetchall()
    for r in rows:
        print(f"  {r['transaction_id']} | {r['transaction_date']} | {r['description'][:40]} | D:{r['debit_amount']} C:{r['credit_amount']}")

    conn.close()


if __name__ == "__main__":
    main()
