import psycopg2

DSN = dict(host="localhost", database="almsdata", user="postgres", password="***REMOVED***")

def main():
    conn = psycopg2.connect(**DSN)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='public'
          AND (table_name ILIKE '%category%' OR table_name ILIKE '%categories%' OR table_name ILIKE '%chart%')
        ORDER BY table_name
        """
    )
    tables = [r[0] for r in cur.fetchall()]
    print("Tables containing category/chart keywords:")
    for t in tables:
        print("  -", t)

    cur.execute(
        """
        SELECT category, COUNT(*) AS cnt
        FROM receipts
        WHERE category IS NOT NULL AND category <> ''
        GROUP BY category
        ORDER BY cnt DESC
        LIMIT 100
        """
    )
    print("\nTop categories in receipts:")
    for cat, cnt in cur.fetchall():
        print(f"  {cat}: {cnt}")

    # Receipt categories reference table (if exists)
    def show_columns(table):
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            ORDER BY ordinal_position
            """,
            (table,),
        )
        return [r[0] for r in cur.fetchall()]

    try:
        cols = show_columns("receipt_categories")
        print("\nreceipt_categories columns:", cols)
        if {"category_id", "category_name", "parent_category"}.issubset(set(cols)):
            cur.execute("SELECT category_id, category_code, category_name, parent_category, display_order FROM receipt_categories ORDER BY category_id")
        else:
            cur.execute("SELECT * FROM receipt_categories ORDER BY 1")
        rows = cur.fetchall()
        print("receipt_categories (first 200):")
        for row in rows[:200]:
            print("  ", row)
    except Exception as e:
        print("\nreceipt_categories query failed:", e)
        conn.rollback()

    # Transaction categories and subcategories
    try:
        cols_tc = show_columns("transaction_categories")
        print("\ntransaction_categories columns:", cols_tc)
        if {"category_id", "category_name"}.issubset(set(cols_tc)):
            cur.execute("SELECT category_id, category_name FROM transaction_categories ORDER BY category_id")
            cats = cur.fetchall()
            print("transaction_categories:")
            for cid, name in cats:
                print(f"  [{cid}] {name}")
        else:
            cur.execute("SELECT * FROM transaction_categories ORDER BY 1")
            rows = cur.fetchall()
            print("transaction_categories (raw first 200):")
            for row in rows[:200]:
                print("  ", row)

        cols_ts = show_columns("transaction_subcategories")
        print("transaction_subcategories columns:", cols_ts)
        if {"subcategory_id", "category_id", "subcategory_name"}.issubset(set(cols_ts)):
            cur.execute("SELECT subcategory_id, category_id, subcategory_name FROM transaction_subcategories ORDER BY category_id, subcategory_id")
            subs = cur.fetchall()
            print("transaction_subcategories:")
            for sid, cid, name in subs:
                print(f"  [{cid}.{sid}] {name}")
        else:
            cur.execute("SELECT * FROM transaction_subcategories ORDER BY 1")
            rows = cur.fetchall()
            print("transaction_subcategories (raw first 200):")
            for row in rows[:200]:
                print("  ", row)
    except Exception as e:
        print("\ntransaction_categories/subcategories query failed:", e)
        conn.rollback()

    # Chart of accounts (id/name) if present
    try:
        cols_coa = show_columns("chart_of_accounts")
        print("\nchart_of_accounts columns:", cols_coa)
        cur.execute("SELECT * FROM chart_of_accounts ORDER BY account_id LIMIT 200")
        rows = cur.fetchall()
        print("chart_of_accounts (first 200):")
        for row in rows:
            print("  ", row)
    except Exception as e:
        print("\nchart_of_accounts query failed:", e)

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
