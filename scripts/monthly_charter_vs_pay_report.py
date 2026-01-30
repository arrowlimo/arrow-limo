#!/usr/bin/env python3
"""
Monthly reconciliation per driver:
- Charter totals: base (driver_base_pay if present else driver_total - gratuity) and gratuity
- Staged pay totals: sum(amount)
- Outputs top gaps per month/driver
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
                    WITH c AS (
                      SELECT date_trunc('month', charter_date)::date AS month,
                             LOWER(COALESCE(NULLIF(TRIM(driver_name),''), NULLIF(TRIM(driver),''))) AS driver_key,
                             SUM(COALESCE(driver_gratuity,0)) AS gratuity_total,
                             SUM(COALESCE(driver_total,0)) AS charter_driver_total,
                             SUM(COALESCE(driver_base_pay, COALESCE(driver_total,0) - COALESCE(driver_gratuity,0))) AS base_total
                      FROM charters
                      WHERE charter_date IS NOT NULL AND cancelled = FALSE AND (driver IS NOT NULL OR driver_name IS NOT NULL)
                      GROUP BY 1,2
                    ), p AS (
                      SELECT date_trunc('month', txn_date)::date AS month,
                             LOWER(TRIM(driver_name)) AS driver_key,
                             SUM(COALESCE(amount,0)) AS pay_total
                      FROM staging_driver_pay
                      WHERE txn_date IS NOT NULL AND driver_name IS NOT NULL
                      GROUP BY 1,2
                    )
                    SELECT c.month, c.driver_key, 
                           c.base_total, c.gratuity_total, c.charter_driver_total,
                           COALESCE(p.pay_total,0) AS pay_total,
                           (COALESCE(p.pay_total,0) - c.charter_driver_total) AS delta_vs_total
                    FROM c
                    LEFT JOIN p ON p.month = c.month AND p.driver_key = c.driver_key
                    ORDER BY c.month DESC, ABS(COALESCE(p.pay_total,0) - c.charter_driver_total) DESC
                    LIMIT 200
                    """
                )
                rows = cur.fetchall()
                print("month | driver | base | gratuity | charter_total | staged_pay | delta")
                for m, d, base, gr, tot, pay, delta in rows:
                    print(f"{m} | {d} | {float(base or 0):,.2f} | {float(gr or 0):,.2f} | {float(tot or 0):,.2f} | {float(pay or 0):,.2f} | {float(delta or 0):,.2f}")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
