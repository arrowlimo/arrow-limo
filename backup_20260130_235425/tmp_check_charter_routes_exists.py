#!/usr/bin/env python3
import os
import psycopg2

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'ArrowLimousine')

TABLES = [
    'charters',
    'charter_routes',
    'charter_route_stops',
    'routes',
    'routing',
]

def main():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    print(f"DB: {DB_NAME} @ {DB_HOST} as {DB_USER}")

    for table in TABLES:
        cur.execute("SELECT to_regclass(%s)", (f'public.{table}',))
        exists = cur.fetchone()[0] is not None
        print(f"\nTable {table}: {'present' if exists else 'missing'}")
        if not exists:
            continue
        cur.execute(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
            """,
            (table,),
        )
        rows = cur.fetchall()
        for col, dtype, nullable, default in rows:
            nulls = 'NULL' if nullable == 'YES' else 'NOT NULL'
            default_str = f" DEFAULT {default}" if default else ''
            print(f"  - {col:30s} {dtype:25s} {nulls}{default_str}")

        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  Rows: {count}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
