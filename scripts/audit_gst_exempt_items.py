#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Audit GST-exempt items across receipts and provide cancelled-charter context.

Goals:
- Find receipts likely misclassified as GST-exempt (gst_amount=0 or is_taxable=false)
- Provide a recommended GST using the included-tax model (AB default 5%)
- Include a separate report listing cancelled charters for the year so that
  GST=0 cases tied to cancellations can be reviewed and excluded from fixes

Outputs (reports/):
- receipts_gst_zero_audit_{year}.csv
- cancelled_charters_gst_context_{year}.csv

Dry-run only; no DB mutations.
"""

import os
import sys
import csv
import argparse
import datetime as dt

try:
    import psycopg2
except Exception:
    print("ERROR: psycopg2 is required.", file=sys.stderr)
    sys.exit(2)


DEFAULT_RATE = 0.05  # Alberta GST

KNOWN_EXEMPT_VENDOR_TOKENS = [
    'charity', 'donation', 'fundraiser', 'raffle', 'contest', 'prize',
    'gov fee', 'government', 'license', 'registration'
]

KNOWN_TAXABLE_VENDOR_TOKENS = [
    'pidherney', 'shell', 'petro', 'esso', 'canadian tire', 'jiffy lube', 'midas',
    'sasktel', 'rogers', 'bell', 'staples', 'woodridge', 'heffner'
]


def db_connect():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REMOVED***')
    port = int(os.getenv('DB_PORT', '5432'))
    return psycopg2.connect(host=host, dbname=name, user=user, password=password, port=port)


def ensure_reports_dir():
    path = os.path.join(os.getcwd(), 'reports')
    os.makedirs(path, exist_ok=True)
    return path


def get_columns(cur, table_name):
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
        """,
        (table_name,)
    )
    return [r[0] for r in cur.fetchall()]


def calculate_gst_included(gross, rate=DEFAULT_RATE):
    try:
        g = float(gross or 0)
        if g <= 0:
            return 0.0, 0.0
        gst = g * rate / (1.0 + rate)
        net = g - gst
        return round(gst, 2), round(net, 2)
    except Exception:
        return 0.0, 0.0


def vendor_tokenize(name):
    return (name or '').lower()


def seems_exempt_vendor(name):
    low = vendor_tokenize(name)
    return any(tok in low for tok in KNOWN_EXEMPT_VENDOR_TOKENS)


def seems_taxable_vendor(name):
    low = vendor_tokenize(name)
    return any(tok in low for tok in KNOWN_TAXABLE_VENDOR_TOKENS)


def audit_receipts(cur, year, vendor_like=None):
    cols = get_columns(cur, 'receipts')
    needed = {'receipt_id', 'vendor_name', 'gross_amount', 'gst_amount', 'net_amount', 'tax_rate', 'is_taxable', 'receipt_date', 'description', 'category'}
    if not needed.issubset(set(cols)):
        return []

    params = [dt.date(year, 1, 1), dt.date(year, 12, 31)]
    where_vendor = ''
    if vendor_like:
        where_vendor = " AND LOWER(vendor_name) LIKE %s"
        params.append('%' + vendor_like.lower() + '%')

    cur.execute(
        f"""
        SELECT receipt_id, vendor_name, receipt_date, category, description,
               gross_amount, COALESCE(gst_amount,0) AS gst_amount,
               COALESCE(net_amount,0) AS net_amount,
               COALESCE(tax_rate,0) AS tax_rate,
               COALESCE(is_taxable,true) AS is_taxable
        FROM receipts
        WHERE receipt_date >= %s AND receipt_date <= %s
          AND (COALESCE(gst_amount,0) = 0 OR COALESCE(is_taxable,true) = false OR COALESCE(tax_rate,0) = 0)
          {where_vendor}
        ORDER BY receipt_date
        """,
        tuple(params)
    )

    out = []
    for rec in cur.fetchall():
        rid, vendor, rdate, cat, desc, gross, gst, net, rate, taxable = rec
        suggested_gst, suggested_net = calculate_gst_included(gross, DEFAULT_RATE)
        reason = []
        if gst == 0:
            reason.append('gst_zero')
        if not taxable:
            reason.append('is_taxable_false')
        if rate == 0:
            reason.append('rate_zero')
        if seems_exempt_vendor(vendor):
            reason.append('vendor_exempt_match')
        if seems_taxable_vendor(vendor):
            reason.append('vendor_taxable_match')

        out.append({
            'receipt_id': rid,
            'vendor_name': vendor,
            'receipt_date': rdate,
            'category': cat,
            'description': desc,
            'gross_amount': float(gross or 0),
            'gst_amount': float(gst or 0),
            'net_amount': float(net or 0),
            'tax_rate': float(rate or 0),
            'is_taxable': taxable,
            'suggested_gst': suggested_gst,
            'suggested_net': suggested_net,
            'flags': '|'.join(reason)
        })
    return out


def cancelled_charters_context(cur, year):
    cols = get_columns(cur, 'charters')
    if 'charter_date' not in cols:
        return []
    cancelled_pred = 'COALESCE(cancelled,false) = true' if 'cancelled' in cols else "LOWER(COALESCE(booking_status,'')) LIKE '%cancel%'"

    cur.execute(
        f"""
        WITH p AS (
            SELECT COALESCE(charter_id, NULL) AS charter_id,
                   reserve_number,
                   ROUND(SUM(COALESCE(amount, payment_amount)), 2) AS total_paid
            FROM payments
            GROUP BY charter_id, reserve_number
        )
        SELECT c.charter_id, c.reserve_number, c.charter_date, c.client_id,
               {cancelled_pred} AS is_cancelled,
               COALESCE(c.balance,0) AS balance,
               COALESCE(p.total_paid,0) AS total_paid,
               COALESCE(c.client_notes,'') || ' ' || COALESCE(c.booking_notes,'') || ' ' || COALESCE(c.notes,'') AS notes
        FROM charters c
        LEFT JOIN p ON (p.charter_id = c.charter_id OR (p.charter_id IS NULL AND p.reserve_number = c.reserve_number))
        WHERE c.charter_date >= %s AND c.charter_date <= %s
          AND {cancelled_pred}
        ORDER BY c.charter_date
        """,
        (dt.date(year, 1, 1), dt.date(year, 12, 31))
    )

    return [
        {
            'charter_id': cid,
            'reserve_number': rn,
            'charter_date': cdate,
            'client_id': clid,
            'is_cancelled': is_c,
            'balance': float(bal or 0),
            'total_paid': float(paid or 0),
            'notes_excerpt': (nt[:200] + '...') if nt and len(nt) > 200 else nt
        }
        for cid, rn, cdate, clid, is_c, bal, paid, nt in cur.fetchall()
    ]


def write_csv(path, rows, fieldnames):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fieldnames})


def main():
    parser = argparse.ArgumentParser(description='Audit GST-exempt receipts and include cancelled charter context.')
    parser.add_argument('--year', type=int, required=True)
    parser.add_argument('--vendor-like', type=str, default=None, help="Optional vendor substring filter (e.g., 'pidhern')")
    args = parser.parse_args()

    year = args.year
    reports = ensure_reports_dir()

    conn = None
    try:
        conn = db_connect()
        cur = conn.cursor()

        receipts = audit_receipts(cur, year, vendor_like=args.vendor_like)
        receipts_csv = os.path.join(reports, f'receipts_gst_zero_audit_{year}.csv')
        write_csv(
            receipts_csv,
            receipts,
            ['receipt_id','vendor_name','receipt_date','category','description','gross_amount','gst_amount','net_amount','tax_rate','is_taxable','suggested_gst','suggested_net','flags']
        )
        print(f"Wrote: {receipts_csv}")

        cancelled = cancelled_charters_context(cur, year)
        cancelled_csv = os.path.join(reports, f'cancelled_charters_gst_context_{year}.csv')
        write_csv(
            cancelled_csv,
            cancelled,
            ['charter_id','reserve_number','charter_date','client_id','is_cancelled','balance','total_paid','notes_excerpt']
        )
        print(f"Wrote: {cancelled_csv}")

        print("Dry-run audit complete. Review CSVs to decide update rules.")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
