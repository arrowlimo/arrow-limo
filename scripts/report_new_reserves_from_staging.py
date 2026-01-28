#!/usr/bin/env python3
"""
Report Reserve_No present in lms_staging_reserve but missing from charters.reserve_number.
Writes CSV to reports/new_reserves_from_staging.csv
"""
import os
import csv
import psycopg2
from dotenv import load_dotenv

load_dotenv()

PG_HOST = os.getenv('DB_HOST','localhost')
PG_PORT = int(os.getenv('DB_PORT','5432'))
PG_NAME = os.getenv('DB_NAME','almsdata')
PG_USER = os.getenv('DB_USER','postgres')
PG_PASSWORD = os.getenv('DB_PASSWORD','')

OUT_CSV = r'l:/limo/reports/new_reserves_from_staging.csv'

def main():
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_NAME, user=PG_USER, password=PG_PASSWORD) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.reserve_no, s.last_updated
                FROM lms_staging_reserve s
                LEFT JOIN charters c ON c.reserve_number = s.reserve_no
                WHERE c.reserve_number IS NULL
                ORDER BY s.last_updated NULLS LAST, s.reserve_no
                """
            )
            rows = cur.fetchall()
    with open(OUT_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['reserve_no','last_updated'])
        w.writerows(rows)
    print(f"Wrote {len(rows)} new reserves to {OUT_CSV}")

if __name__ == '__main__':
    main()
