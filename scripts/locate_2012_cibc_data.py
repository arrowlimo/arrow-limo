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

    # Identify candidate CIBC bank_accounts rows
    print("\n[bank_accounts] CIBC candidates:")
    cur.execute(
        """
        select bank_id, account_name, institution_name, account_number
        from bank_accounts
        where (institution_name ilike '%CIBC%'
               or account_name ilike '%CIBC%'
               or account_number ilike '%0228362%'
               or account_number ilike '%61615%'
               or account_number ilike '%74-61615%')
        order by bank_id
        """
    )
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f" - bank_id={r['bank_id']}, name={r['account_name']}, inst={r['institution_name']}, acct={r['account_number']}")
    else:
        print(" - (none)")

    # banking_transactions: 2012 counts by bank_id/account_number
    print("\n[banking_transactions] 2012 counts by bank_id/account_number:")
    cur.execute(
        """
        select bt.bank_id,
               coalesce(bt.account_number,'(null)') as account_number,
               count(*) as cnt,
               min(bt.transaction_date) as min_dt,
               max(bt.transaction_date) as max_dt
        from banking_transactions bt
        where bt.transaction_date >= date '2012-01-01' and bt.transaction_date < date '2013-01-01'
        group by bt.bank_id, coalesce(bt.account_number,'(null)')
        order by cnt desc
        limit 20
        """
    )
    rows = cur.fetchall()
    for r in rows:
        print(f" - bank_id={r['bank_id']}, acct={r['account_number']}, cnt={r['cnt']}, range=[{r['min_dt']},{r['max_dt']}]")

    # Join to bank_accounts for readability
    print("\n[banking_transactions] 2012 counts with bank account names:")
    cur.execute(
        """
        select ba.bank_id, ba.account_name, ba.institution_name, ba.account_number as ba_account,
               count(*) as cnt
        from banking_transactions bt
        join bank_accounts ba on ba.bank_id = bt.bank_id
        where bt.transaction_date >= date '2012-01-01' and bt.transaction_date < date '2013-01-01'
        group by ba.bank_id, ba.account_name, ba.institution_name, ba.account_number
        order by cnt desc
        limit 10
        """
    )
    rows = cur.fetchall()
    for r in rows:
        print(f" - bank_id={r['bank_id']}, name={r['account_name']}, inst={r['institution_name']}, acct={r['ba_account']}, cnt={r['cnt']}")

    # Sample a few January rows for the top CIBC bank_id (heuristic: institution_name contains CIBC)
    print("\n[banking_transactions] Sample January 2012 rows for CIBC-mapped account:")
    cur.execute(
        """
        with cibc_ids as (
            select bank_id from bank_accounts where institution_name ilike '%CIBC%'
        )
        select bt.transaction_id, bt.transaction_date, bt.description, bt.debit_amount, bt.credit_amount, bt.balance, bt.account_number, bt.bank_id
        from banking_transactions bt
        where bt.bank_id in (select bank_id from cibc_ids)
          and bt.transaction_date >= date '2012-01-01' and bt.transaction_date < date '2012-02-01'
        order by bt.transaction_date, bt.transaction_id
        limit 10
        """
    )
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(
                f" - id={r['transaction_id']}, date={r['transaction_date']}, desc={r['description']}, "
                f"debit={r['debit_amount']}, credit={r['credit_amount']}, bal={r['balance']}, acctnum={r['account_number']}, bank_id={r['bank_id']}"
            )
    else:
        print(" - (no rows for January 2012 under CIBC)")

    # List 1615 backup tables and their row counts for 2012
    print("\n[1615 backup tables] existence and 2012 counts (approx):")
    cur.execute(
        """
        select table_name
        from information_schema.tables
        where table_schema='public' and table_name ilike 'banking_transactions_1615%'
        order by table_name
        """
    )
    tbls = [r[0] for r in cur.fetchall()]
    if not tbls:
        print(" - (none)")
    else:
        for t in tbls:
            try:
                cur.execute(f"select count(*) from {t}")
                c = cur.fetchone()[0]
                print(f" - {t}: {c} rows")
            except Exception as e:
                print(f" - {t}: count failed: {e}")

    conn.close()


if __name__ == "__main__":
    main()
