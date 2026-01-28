#!/usr/bin/env python3
"""
Inspect DB schema relevant to linking Square payments to charters.
Prints columns for payments and charters, plus a few sample rows.
Uses .env for DB connection.
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv('l:/limo/.env')
load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')

def main():
    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    def cols(table):
        cur.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            ORDER BY ordinal_position
            """,
            (table,)
        )
        return cur.fetchall()

    for tbl in ['payments','charters']:
        try:
            print(f"\n== {tbl} ==")
            for c,t in cols(tbl):
                print(f" - {c}: {t}")
        except Exception as e:
            print(f"[error] {tbl}: {e}")

    # Sample payments (Square)
    try:
        cur.execute("SELECT payment_key, amount, payment_date, charter_id, notes FROM payments WHERE payment_key IS NOT NULL ORDER BY last_updated DESC LIMIT 10")
        rows = cur.fetchall()
        print("\nSample payments:")
        for r in rows:
            print(r)
    except Exception as e:
        print('[error] payments sample:', e)

    # Sample charters metadata
    try:
        cur.execute("SELECT COUNT(*) FROM charters")
        count = cur.fetchone()[0]
        print(f"\nCharters count: {count}")
        cur.execute("SELECT * FROM charters ORDER BY charter_date DESC NULLS LAST LIMIT 3")
        # print column names
        names = [d[0] for d in cur.description]
        for row in cur.fetchall():
            print(dict(zip(names, row)))
    except Exception as e:
        print('[error] charters sample:', e)

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
