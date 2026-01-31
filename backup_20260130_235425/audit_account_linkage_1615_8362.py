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


def exists(cur, schema: str, name: str, kind: str = "table") -> bool:
    if kind == "table":
        cur.execute(
            """
            select 1
            from information_schema.tables
            where table_schema=%s and table_name=%s
            """,
            (schema, name),
        )
    else:
        cur.execute(
            """
            select 1
            from information_schema.views
            where table_schema=%s and table_name=%s
            """,
            (schema, name),
        )
    return cur.fetchone() is not None


def main():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    print("Connected.")

    # 1) 2012 counts and bank_id distribution for both accounts
    print("\n[banking_transactions] 2012 by account_number and bank_id:")
    cur.execute(
        """
        select account_number, bank_id, count(*) as cnt,
               min(transaction_date) as min_dt, max(transaction_date) as max_dt
        from banking_transactions
        where transaction_date >= date '2012-01-01' and transaction_date < date '2013-01-01'
          and account_number in ('1615','0228362','74-61615')
        group by account_number, bank_id
        order by account_number, bank_id nulls first
        """
    )
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(
                f" - acct={r['account_number']}, bank_id={r['bank_id']}, cnt={r['cnt']}, range=[{r['min_dt']},{r['max_dt']}]"
            )
    else:
        print(" - (no rows)")

    # 2) bank_accounts presence for 0228362 and 74-61615
    print("\n[bank_accounts] presence for 0228362 and 74-61615:")
    cur.execute(
        """
        select bank_id, account_name, institution_name, account_number
        from bank_accounts
        where account_number in ('0228362','74-61615','61615')
        order by bank_id
        """
    )
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(
                f" - bank_id={r['bank_id']}, name={r['account_name']}, inst={r['institution_name']}, acct={r['account_number']}"
            )
    else:
        print(" - (none)")

    # 3) account_number_aliases links (dynamic columns)
    print("\n[account_number_aliases] potential links involving 1615 and 0228362:")
    if exists(cur, 'public', 'account_number_aliases', kind='table'):
        cur.execute(
            """
            select column_name
            from information_schema.columns
            where table_schema='public' and table_name='account_number_aliases'
            order by ordinal_position
            """
        )
        cols = [r[0] for r in cur.fetchall()]
        print(" - columns:", ", ".join(cols))
        alias_col = None
        canonical_col = None
        for cand in ("alias", "alias_account_number", "alias_number", "alias_acct"):
            if cand in cols:
                alias_col = cand
                break
        for cand in ("canonical_account_number", "canonical", "canonical_number", "canonical_acct"):
            if cand in cols:
                canonical_col = cand
                break
        if alias_col and canonical_col:
            q = f"""
                select {alias_col} as alias, {canonical_col} as canonical
                from account_number_aliases
                where ({alias_col} ilike '%1615%' or {alias_col} ilike '%0228362%' or {canonical_col} ilike '%1615%' or {canonical_col} ilike '%0228362%')
                order by {alias_col}, {canonical_col}
            """
            cur.execute(q)
            rows = cur.fetchall()
            if rows:
                for r in rows:
                    print(f" - alias={r['alias']} -> canonical={r['canonical']}")
            else:
                print(" - (no aliases found for these patterns)")
        else:
            # Fallback: scan any text columns for 1615/0228362
            text_cols = [c for c in cols if c not in (None,) ]
            like = " OR ".join([f"cast({c} as text) ilike '%1615%' OR cast({c} as text) ilike '%0228362%'" for c in text_cols])
            cur.execute(f"select * from account_number_aliases where {like} limit 20")
            rows = cur.fetchall()
            if rows:
                print(f" - {len(rows)} rows mention 1615/0228362 (first 5 shown):")
                for r in rows[:5]:
                    print("   * ", {k: r[k] for k in r.keys() if k in text_cols})
            else:
                print(" - (no textual matches in alias table)")
    else:
        print(" - table not found")

    # 4) v_banking_transactions_with_aliases behavior (if exists)
    print("\n[v_banking_transactions_with_aliases] canonicalization check:")
    if exists(cur, 'public', 'v_banking_transactions_with_aliases', kind='view'):
        cur.execute(
            """
            select canonical_account_number, count(*) as cnt
            from v_banking_transactions_with_aliases
            where transaction_date >= date '2012-01-01' and transaction_date < date '2013-01-01'
              and (account_number in ('1615','0228362','74-61615') or canonical_account_number in ('1615','0228362','74-61615'))
            group by canonical_account_number
            order by cnt desc
            """
        )
        rows = cur.fetchall()
        if rows:
            for r in rows:
                print(f" - canonical={r['canonical_account_number']}, cnt={r['cnt']}")
        else:
            print(" - (no rows)")
    else:
        print(" - view not found")

    conn.close()
    print("\nAudit complete.")


if __name__ == "__main__":
    main()
