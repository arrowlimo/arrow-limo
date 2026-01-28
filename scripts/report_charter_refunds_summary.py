#!/usr/bin/env python3
"""
Produce a refund tracking summary per charter and write CSV.
- Reads charter_refunds + payments totals per charter
- Outputs: reports/charter_refunds_summary.csv
"""
import os
import csv
import psycopg2
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')

OUTPUT = r'l:\limo\reports\charter_refunds_summary.csv'

SQL = """
WITH pay AS (
  SELECT reserve_number, SUM(COALESCE(amount, payment_amount)) AS payments_total
  FROM payments
  GROUP BY reserve_number
), ref AS (
  SELECT reserve_number, SUM(amount) AS refunds_total, COUNT(*) AS refund_count
  FROM charter_refunds
  GROUP BY reserve_number
)
SELECT c.reserve_number,
       c.charter_id,
       COALESCE(pay.payments_total,0) AS payments_total,
       COALESCE(ref.refunds_total,0) AS refunds_total,
       COALESCE(ref.refund_count,0)  AS refund_count,
       COALESCE(pay.payments_total,0) - COALESCE(ref.refunds_total,0) AS net_collected
FROM charters c
LEFT JOIN pay ON pay.reserve_number = c.reserve_number
LEFT JOIN ref ON ref.reserve_number = c.reserve_number
WHERE (COALESCE(ref.refund_count,0) > 0)
ORDER BY refunds_total DESC
"""

def main():
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    cur.execute(SQL)
    rows = cur.fetchall()
    headers = [d.name for d in cur.description]

    with open(OUTPUT,'w',encoding='utf-8',newline='') as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            w.writerow(r)
    print(f"✓ Refund summary written: {OUTPUT} ({len(rows)} rows)")

    # Quick console snapshot
    top = rows[:10]
    for r in top:
        rn, cid, pt, rt, rc, net = r
        print(f"  {rn} | refunds ${rt:,.2f} (n={rc}) | payments ${pt:,.2f} | net ${net:,.2f}")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
