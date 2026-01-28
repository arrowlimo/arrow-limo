#!/usr/bin/env python3
"""
Report 2019 receipts related to shop/parking rent.

Filters:
- receipt_date between 2019-01-01 and 2019-12-31
- category ILIKE '%rent%'
  OR vendor_name ILIKE '%woodrow%'
  OR description ILIKE any of ('%rent%', '%shop%', '%parking%')

Outputs:
- Monthly totals summary
- Detailed list (date, vendor, category, gross, gst, created_from_banking, source_reference)
- Duplicate candidates (same date + amount + vendor)
"""

import os
import psycopg2

DB = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***'),
)

START = '2019-01-01'
END = '2020-01-01'

with psycopg2.connect(**DB) as conn:
    with conn.cursor() as cur:
        print('='*100)
        print('2019 SHOP/PARKING RENT RECEIPTS')
        print('='*100)

        # Monthly totals
        cur.execute(
            """
            SELECT to_char(date_trunc('month', receipt_date), 'YYYY-MM') AS ym,
                   COUNT(*) AS cnt,
                   COALESCE(SUM(gross_amount),0) AS total_gross,
                   COALESCE(SUM(gst_amount),0) AS total_gst
            FROM receipts
            WHERE receipt_date >= %s AND receipt_date < %s
              AND (
                category ILIKE '%%rent%%'
                OR vendor_name ILIKE '%%woodrow%%'
                OR description ILIKE '%%rent%%'
                OR description ILIKE '%%shop%%'
                OR description ILIKE '%%parking%%'
              )
            GROUP BY 1
            ORDER BY 1
            """,
            (START, END)
        )
        rows = cur.fetchall()
        if rows:
            print(f"\n{'Month':<10s} {'Count':>6s} {'Gross':>12s} {'GST':>10s}")
            print('-'*60)
            for ym, cnt, gross, gst in rows:
                print(f"{ym:<10s} {cnt:>6d} ${float(gross):>10.2f} ${float(gst):>8.2f}")
        else:
            print('No matching receipts found for 2019.')

        # Detailed list
        print('\nDETAILS:')
        print('-'*100)
        cur.execute(
            """
            SELECT id, receipt_date, vendor_name, category, gross_amount, gst_amount,
                   created_from_banking, source_reference, description
            FROM receipts
            WHERE receipt_date >= %s AND receipt_date < %s
              AND (
                category ILIKE '%%rent%%'
                OR vendor_name ILIKE '%%woodrow%%'
                OR description ILIKE '%%rent%%'
                OR description ILIKE '%%shop%%'
                OR description ILIKE '%%parking%%'
              )
            ORDER BY receipt_date, id
            """,
            (START, END)
        )
    rows = cur.fetchall()
    for rid, dt, vendor, category, gross, gst, from_bank, src_ref, desc in rows:
      fb = 'Y' if from_bank else 'N'
      v = (vendor or '')
      c = (category or '')
      d = (desc or '')
      print(f"  {dt} | ID {rid:<6d} | {v:<20.20s} | {c:<14.14s} | ${float(gross or 0):>8.2f} | GST ${float(gst or 0):>6.2f} | bank={fb} | ref={src_ref or ''} | {d[:60]}")

    # Duplicates by (date, vendor, gross)
    print('\nPOSSIBLE DUPLICATES (same date+vendor+gross):')
    print('-'*100)
    cur.execute(
        """
        SELECT receipt_date, vendor_name, gross_amount, COUNT(*) AS cnt,
               array_agg(id ORDER BY id) AS ids
        FROM receipts
        WHERE receipt_date >= %s AND receipt_date < %s
              AND (
                category ILIKE '%%rent%%'
                OR vendor_name ILIKE '%%woodrow%%'
                OR description ILIKE '%%rent%%'
                OR description ILIKE '%%shop%%'
                OR description ILIKE '%%parking%%'
              )
        GROUP BY receipt_date, vendor_name, gross_amount
        HAVING COUNT(*) > 1
        ORDER BY receipt_date
        """,
        (START, END)
    )
    dup_rows = cur.fetchall()
    if dup_rows:
        for dt, vendor, gross, cnt, ids in dup_rows:
            print(f"  {dt} | {vendor} | ${float(gross or 0):.2f} | count={cnt} | ids={list(ids)}")
    else:
        print('  None found.')
