#!/usr/bin/env python3
"""
Analyze staging_driver_pay coverage: how many rows have txn_date, broken down by file_type.
"""
import os
import psycopg2

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REDACTED***')


def connect_db():
    return psycopg2.connect(dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD)


def main():
    conn = connect_db()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT f.file_type,
                           COUNT(*) AS total_rows,
                           SUM(CASE WHEN p.txn_date IS NOT NULL THEN 1 ELSE 0 END) AS with_date,
                           SUM(CASE WHEN p.driver_name IS NOT NULL THEN 1 ELSE 0 END) AS with_driver_name
                    FROM staging_driver_pay p
                    JOIN staging_driver_pay_files f ON f.id = p.file_id
                    GROUP BY f.file_type
                    ORDER BY total_rows DESC
                    """
                )
                print("file_type | total | with_date | with_driver_name")
                for ft, total, wd, wdn in cur.fetchall():
                    print(f"{ft} | {total:,} | {wd:,} | {wdn:,}")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
