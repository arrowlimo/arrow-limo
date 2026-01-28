import os
import sys
from typing import List, Tuple

import psycopg2
import psycopg2.extras


def get_conn():
    host = os.environ.get("DB_HOST", "localhost")
    db = os.environ.get("DB_NAME", "almsdata")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "***REMOVED***")
    return psycopg2.connect(host=host, dbname=db, user=user, password=password)


def list_candidate_tables(cur) -> List[str]:
    cur.execute(
        """
        select table_name
        from information_schema.tables
        where table_schema='public'
          and (table_name ilike '%bank%'
               or table_name ilike '%account%'
               or table_name ilike '%transact%')
        order by 1
        """
    )
    return [r[0] for r in cur.fetchall()]


def table_exists(cur, name: str) -> bool:
    cur.execute(
        "select 1 from information_schema.tables where table_schema='public' and table_name=%s",
        (name,),
    )
    return cur.fetchone() is not None


def get_columns(cur, table: str) -> List[Tuple[str, str]]:
    cur.execute(
        """
        select column_name, data_type
        from information_schema.columns
        where table_schema='public' and table_name=%s
        order by ordinal_position
        """,
        (table,),
    )
    return [(r[0], r[1]) for r in cur.fetchall()]


def find_date_column(cols: List[Tuple[str, str]]) -> str:
    for name, dtype in cols:
        if dtype in ("date", "timestamp without time zone", "timestamp with time zone"):
            if any(k in name for k in ("date", "posted", "trans", "txn")):
                return name
    # fallback: any date/timestamp
    for name, dtype in cols:
        if dtype in ("date", "timestamp without time zone", "timestamp with time zone"):
            return name
    return ""


def main():
    try:
        conn = get_conn()
    except Exception as e:
        print("DB CONNECT ERROR:", e)
        sys.exit(2)

    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    print("Connected to DB.")

    tables = list_candidate_tables(cur)
    print("Candidate tables:", ", ".join(tables) or "(none)")

    # bank_accounts check
    if table_exists(cur, "bank_accounts"):
        print("bank_accounts: exists")
        cols = get_columns(cur, "bank_accounts")
        print("bank_accounts columns:", ", ".join(c for c, _ in cols))
        try:
            cur.execute("select * from bank_accounts limit 200")
            rows = cur.fetchall()
            hit_rows = []
            for row in rows:
                if any(isinstance(v, str) and ("61615" in v or "74-61615" in v) for v in row):
                    hit_rows.append(dict(row))
            if hit_rows:
                print(f"bank_accounts rows mentioning 61615: {len(hit_rows)}")
                for r in hit_rows[:5]:
                    print(" - ", {k: v for k, v in r.items() if isinstance(v, (str, int))})
            else:
                print("bank_accounts: no values containing 61615 in first 200 rows")
        except Exception as e:
            print("bank_accounts sample read failed:", e)
    else:
        print("bank_accounts: missing")

    # banking_transactions check
    if table_exists(cur, "banking_transactions"):
        print("banking_transactions: exists")
        cols = get_columns(cur, "banking_transactions")
        print("banking_transactions columns:", ", ".join(c for c, _ in cols))
        text_cols = [c for c, t in cols if t in ("text", "character varying", "character")]
        date_col = find_date_column(cols)
        where_year = ""
        params = []
        if date_col:
            where_year = f" and {date_col} >= %s and {date_col} < %s"
            params.extend(["2012-01-01", "2013-01-01"])
            print(f"Using date filter on {date_col} for 2012 window")
        if text_cols:
            like_clause = " OR ".join([f"{c} ilike '%61615%'" for c in text_cols])
            q = f"select count(*) from banking_transactions where ({like_clause}){where_year}"
            try:
                cur.execute(q, params)
                cnt = cur.fetchone()[0]
                print("banking_transactions rows mentioning 61615 in any text col:", cnt)
            except Exception as e:
                print("61615 search failed:", e)
        # Account number column direct
        if any(c == "account_number" for c, _ in cols):
            try:
                q = f"select count(*) from banking_transactions where account_number ilike '%61615%'"
                if where_year:
                    q += where_year.replace(" and ", " and ")
                cur.execute(q, params)
                print("banking_transactions.account_number like 61615:", cur.fetchone()[0])
            except Exception as e:
                print("account_number search failed:", e)
    else:
        print("banking_transactions: missing")

    conn.close()


if __name__ == "__main__":
    main()
