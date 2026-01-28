#!/usr/bin/env python3
import os
import psycopg2

DB = dict(
    dbname=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
    host=os.environ.get('DB_HOST', 'localhost'),
    port=int(os.environ.get('DB_PORT', '5432')),
)

EXEMPT = {'Z','EXCL','EXEMPT','NO GST','GST EXEMPT','GST EXCL'}

sql = """
WITH base AS (
  SELECT 
    COALESCE(gst_amount,0) AS gst,
    UPPER(COALESCE(gst_code,'')) AS code
  FROM receipts
), flags AS (
  SELECT 
    (code IN %s) AS is_exempt,
    (gst = 0) AS is_zero
  FROM base
)
SELECT 
  SUM(CASE WHEN NOT is_exempt AND is_zero THEN 1 ELSE 0 END) AS zero_non_exempt,
  SUM(CASE WHEN NOT is_exempt AND NOT is_zero THEN 1 ELSE 0 END) AS nonzero_non_exempt,
  SUM(CASE WHEN is_exempt AND is_zero THEN 1 ELSE 0 END) AS exempt_zero,
  SUM(CASE WHEN is_exempt AND NOT is_zero THEN 1 ELSE 0 END) AS exempt_nonzero,
  COUNT(*) AS total
FROM flags;
"""

def main():
    conn = psycopg2.connect(**DB)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, (tuple(EXEMPT),))
                row = cur.fetchone()
                print({
                    'zero_non_exempt': row[0],
                    'nonzero_non_exempt': row[1],
                    'exempt_zero': row[2],
                    'exempt_nonzero': row[3],
                    'total': row[4],
                })
    finally:
        conn.close()

if __name__ == '__main__':
    main()
