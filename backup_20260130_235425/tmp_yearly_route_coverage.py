#!/usr/bin/env python3
import os
import psycopg2

def main():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        dbname=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','ArrowLimousine'),
    )
    cur = conn.cursor()
    cur.execute(
        """
        WITH yr AS (
          SELECT generate_series(2020, 2026) AS y
        ), base AS (
          SELECT y,
                 COUNT(*) FILTER (WHERE c.charter_date IS NOT NULL AND EXTRACT(YEAR FROM c.charter_date)=y) AS charters,
                 COUNT(cr.route_id) FILTER (WHERE c.charter_date IS NOT NULL AND EXTRACT(YEAR FROM c.charter_date)=y) AS routes
          FROM yr
          LEFT JOIN charters c ON EXTRACT(YEAR FROM c.charter_date)=y
          LEFT JOIN charter_routes cr ON cr.charter_id = c.charter_id
          GROUP BY y
        )
        SELECT y, charters, routes, (charters - routes) AS missing
        FROM base
        ORDER BY y;
        """
    )
    rows = cur.fetchall()
    print("Year | charters | routes | missing")
    for y, ch, rt, miss in rows:
        print(f"{int(y)} | {ch} | {rt} | {miss}")
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
