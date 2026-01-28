#!/usr/bin/env python3
"""
Monthly reconciliation per driver using alias normalization:
- Canonicalize driver keys for both charters and staging using driver_alias_map when available,
  otherwise fall back to a SQL normalization that strips 'driver' and leading 'dr'.
- Aggregates monthly charter base/gratuity/total and staged pay totals; prints top gaps.
"""
import os
import psycopg2

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REMOVED***')


def connect_db():
    return psycopg2.connect(dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD)

SQL = r"""
WITH
norm_charters AS (
  SELECT
    date_trunc('month', charter_date)::date AS month,
    /* normalize: lower -> remove 'driver' -> strip leading 'dr' */
    CASE
      WHEN COALESCE(NULLIF(BTRIM(driver_name),''), NULLIF(BTRIM(driver),'')) IS NULL THEN NULL
      ELSE LOWER(
        REGEXP_REPLACE(
          REPLACE(COALESCE(NULLIF(BTRIM(driver_name),''), NULLIF(BTRIM(driver),'')), 'driver', ''),
          '^dr',
          '',
          'i'
        )
      )
    END AS driver_key,
    SUM(COALESCE(driver_base_pay, COALESCE(driver_total,0) - COALESCE(driver_gratuity,0))) AS base_total,
    SUM(COALESCE(driver_gratuity,0)) AS gratuity_total,
    SUM(COALESCE(driver_total,0)) AS charter_total
  FROM charters
  WHERE charter_date IS NOT NULL AND cancelled = FALSE AND (driver IS NOT NULL OR driver_name IS NOT NULL)
  GROUP BY 1,2
),
charters_canon AS (
  SELECT c.month,
         COALESCE(a.canonical_name, c.driver_key) AS driver_canon,
         c.base_total, c.gratuity_total, c.charter_total
  FROM norm_charters c
  LEFT JOIN driver_alias_map a ON a.driver_key = c.driver_key
),
norm_pay AS (
  SELECT
    date_trunc('month', txn_date)::date AS month,
    CASE WHEN driver_name IS NULL THEN NULL
         ELSE LOWER(
           REGEXP_REPLACE(REPLACE(BTRIM(driver_name),'driver',''), '^dr', '', 'i')
         ) END AS driver_key,
    SUM(COALESCE(amount,0)) AS pay_total
  FROM staging_driver_pay
  WHERE txn_date IS NOT NULL AND driver_name IS NOT NULL
  GROUP BY 1,2
),
pay_canon AS (
  SELECT p.month,
         COALESCE(a.canonical_name, p.driver_key) AS driver_canon,
         p.pay_total
  FROM norm_pay p
  LEFT JOIN driver_alias_map a ON a.driver_key = p.driver_key
)
SELECT c.month,
       c.driver_canon,
       c.base_total,
       c.gratuity_total,
       c.charter_total,
       COALESCE(p.pay_total, 0) AS pay_total,
       (COALESCE(p.pay_total,0) - c.charter_total) AS delta_vs_total
FROM charters_canon c
LEFT JOIN pay_canon p ON p.month = c.month AND p.driver_canon = c.driver_canon
ORDER BY c.month DESC, ABS(COALESCE(p.pay_total,0) - c.charter_total) DESC
LIMIT 300;
"""


def main():
    conn = connect_db()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(SQL)
                rows = cur.fetchall()
                print("month | driver | base | gratuity | charter_total | staged_pay | delta")
                for m, d, base, gr, tot, pay, delta in rows:
                    print(f"{m} | {d} | {float(base or 0):,.2f} | {float(gr or 0):,.2f} | {float(tot or 0):,.2f} | {float(pay or 0):,.2f} | {float(delta or 0):,.2f}")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
