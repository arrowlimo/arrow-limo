#!/usr/bin/env python
import psycopg2
RESERVES = ['015901','015902','012861','016011','016021','016009','016010','016022']
DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    for res in RESERVES:
        cur.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(COALESCE(amount,0)+COALESCE(gst_amount,0)),0)
            FROM charter_charges
            WHERE reserve_number = %s
            """,
            (res,)
        )
        row = cur.fetchone()
        print(f"{res}: count={row[0]}, total={row[1]:.2f}")
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
