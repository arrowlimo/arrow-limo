#!/usr/bin/env python3
import pathlib
import sys
from pprint import pprint

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api import get_db_connection  # type: ignore


def main():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='banking_transactions'
        ORDER BY ordinal_position
    """)
    cols = cur.fetchall()
    print("Columns (banking_transactions):")
    for name, dtype in cols:
        print(f" - {name} ({dtype})")

    # Show a few 2015 rows
    cur.execute("""
        SELECT * FROM banking_transactions
        WHERE transaction_date >= DATE '2015-01-01' AND transaction_date < DATE '2016-01-01'
        ORDER BY transaction_date
        LIMIT 5
    """)
    rows = cur.fetchall()
    colnames = [d[0] for d in cur.description]

    print("\nSample 2015 rows:")
    for r in rows:
        rec = {colnames[i]: r[i] for i in range(len(colnames))}
        pprint(rec)
        print()

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
