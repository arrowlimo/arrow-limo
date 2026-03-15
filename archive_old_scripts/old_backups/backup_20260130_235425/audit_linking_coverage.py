#!/usr/bin/env python3
"""
Audit current charter-payment linking coverage vs historical expectations.
Outputs a small summary to stdout and writes a CSV with link rates by method and recency.
"""
import os
import csv
from datetime import date, timedelta
import psycopg2
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')
CSV_OUT = 'l:/limo/reports/linking_coverage_summary.csv'
LOOKBACK_DAYS = int(os.getenv('SQUARE_LOOKBACK_DAYS','120'))


def get_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def fetch_coverage(cur):
    cur.execute("SELECT COUNT(*) FROM payments")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM payments WHERE reserve_number IS NOT NULL")
    linked = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM payments WHERE payment_date >= CURRENT_DATE - INTERVAL '%s days'" % LOOKBACK_DAYS)
    total_recent = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM payments WHERE reserve_number IS NOT NULL AND payment_date >= CURRENT_DATE - INTERVAL '%s days'" % LOOKBACK_DAYS)
    linked_recent = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(LOWER(payment_method),'(null)') AS method,
               COUNT(*) AS total,
               COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) AS linked
          FROM payments
      GROUP BY COALESCE(LOWER(payment_method),'(null)')
      ORDER BY total DESC
    """)
    by_method = cur.fetchall()

    # Check for any prior reconciliation artifacts
    cur.execute("SELECT to_regclass('public.charter_payment_references')")
    has_refs = cur.fetchone()[0] is not None

    cur.execute("SELECT to_regclass('public.charter_payment_reconciliation_summary')")
    has_view = cur.fetchone()[0] is not None

    # Square e-transfer reconciliation table (mentioned in logs)
    cur.execute("SELECT to_regclass('public.square_etransfer_reconciliation')")
    has_sq_e = cur.fetchone()[0] is not None
    sq_e_rows = 0
    if has_sq_e:
        cur.execute("SELECT COUNT(*) FROM square_etransfer_reconciliation")
        sq_e_rows = cur.fetchone()[0]

    return {
        'total': total,
        'linked': linked,
        'total_recent': total_recent,
        'linked_recent': linked_recent,
        'by_method': by_method,
        'has_charter_payment_references': has_refs,
        'has_charter_payment_reconciliation_summary': has_view,
        'has_square_etransfer_reconciliation': has_sq_e,
        'square_etransfer_rows': sq_e_rows,
    }


def write_csv(summary):
    os.makedirs(os.path.dirname(CSV_OUT), exist_ok=True)
    with open(CSV_OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['metric','value'])
        w.writerow(['payments_total', summary['total']])
        w.writerow(['payments_linked', summary['linked']])
        overall = round(100.0*summary['linked']/summary['total'], 2) if summary['total'] else 0.0
        w.writerow(['overall_link_rate_percent', overall])
        w.writerow(['payments_recent_total', summary['total_recent']])
        w.writerow(['payments_recent_linked', summary['linked_recent']])
        recent_rate = round(100.0*summary['linked_recent']/summary['total_recent'], 2) if summary['total_recent'] else 0.0
        w.writerow(['recent_link_rate_percent', recent_rate])
        w.writerow([])
        w.writerow(['method','total','linked','link_rate_percent'])
        for method, total, linked in summary['by_method']:
            rate = round(100.0*linked/total, 2) if total else 0.0
            w.writerow([method, total, linked, rate])
        w.writerow([])
        w.writerow(['has_charter_payment_references', summary['has_charter_payment_references']])
        w.writerow(['has_charter_payment_reconciliation_summary', summary['has_charter_payment_reconciliation_summary']])
        w.writerow(['has_square_etransfer_reconciliation', summary['has_square_etransfer_reconciliation']])
        w.writerow(['square_etransfer_rows', summary['square_etransfer_rows']])


def main():
    with get_conn() as conn:
        with conn.cursor() as cur:
            s = fetch_coverage(cur)
    write_csv(s)
    print('Coverage summary written to', CSV_OUT)
    print({k: v for k, v in s.items() if k != 'by_method'})

if __name__ == '__main__':
    main()
