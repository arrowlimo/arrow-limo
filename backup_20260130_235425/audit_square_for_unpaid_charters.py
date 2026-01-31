"""
Audit Square payments for a provided list of reserve_numbers (CSV from
export_unpaid_charters_with_driver_pay.py). Reports:
 - Direct Square payments linked to the same reserve_number
 - Nearby Square payments by the same client within +/- 45 days of charter_date

Outputs a CSV report in reports/ and prints a short summary.
"""
import os
import csv
from datetime import datetime, timedelta
import argparse
import psycopg2


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def load_reserve_numbers(csv_path):
    reserves = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        # Normalized header name per exporter: 'reserve_number'
        for row in r:
            rn = (row.get('reserve_number') or '').strip()
            if rn:
                reserves.append(rn)
    # De-duplicate, preserve order
    seen = set()
    uniq = []
    for rn in reserves:
        if rn not in seen:
            uniq.append(rn)
            seen.add(rn)
    return uniq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True, help='Path to CSV from unpaid-with-charges export')
    ap.add_argument('--window-days', type=int, default=45, help='+/- days around charter_date to consider adjacent Square payments for same client')
    args = ap.parse_args()

    reserves = load_reserve_numbers(args.input)
    if not reserves:
        print('No reserve numbers found in input CSV.')
        return

    conn = connect(); cur = conn.cursor()

    # Gather basic charter info for these reserves
    cur.execute(
        """
        SELECT c.reserve_number::text, c.charter_id, c.client_id, CAST(c.charter_date AS DATE) AS charter_date
        FROM charters c
        WHERE c.reserve_number::text = ANY(%s)
        """,
        (reserves,)
    )
    charter_rows = cur.fetchall()
    if not charter_rows:
        print('No matching charters found for provided reserves.')
        cur.close(); conn.close(); return

    charter_info = {r[0]: {'charter_id': r[1], 'client_id': r[2], 'charter_date': r[3]} for r in charter_rows}

    # Direct Square payments linked to same reserve_number
    cur.execute(
        """
        SELECT p.reserve_number::text AS reserve_number,
               p.payment_id, p.payment_date, p.payment_method,
               COALESCE(p.amount, p.payment_amount) AS amount,
               p.square_payment_id, p.square_last4, p.square_card_brand, p.square_status, p.notes
        FROM payments p
        WHERE p.reserve_number::text = ANY(%s)
          AND (
            p.square_payment_id IS NOT NULL OR p.square_status IS NOT NULL OR
            p.square_last4 IS NOT NULL OR p.square_card_brand IS NOT NULL
          )
        ORDER BY p.payment_date NULLS LAST, p.payment_id
        """,
        (reserves,)
    )
    direct_rows = cur.fetchall()

    # Adjacent Square payments for same client within window-days
    # Join by client_id; allow any reserve_number (including NULL or different)
    # We'll fetch all and filter by charter window per-row
    adjacent_records = []
    for rn, info in charter_info.items():
        client_id = info['client_id']
        cdate = info['charter_date']
        if client_id is None or cdate is None:
            continue
        start = cdate - timedelta(days=args.window_days)
        end = cdate + timedelta(days=args.window_days)
        cur.execute(
            """
            SELECT %s AS reserve_number,
                   c.charter_id AS charter_id,
                   c.client_id AS client_id,
                   c.charter_date AS charter_date,
                   p.payment_id, p.payment_date,
                   COALESCE(p.amount, p.payment_amount) AS amount,
                   p.reserve_number::text AS payment_reserve,
                   p.payment_method,
                   p.square_payment_id, p.square_last4, p.square_card_brand, p.square_status, p.notes
            FROM payments p
            JOIN charters c ON c.client_id = p.client_id
            WHERE c.reserve_number::text = %s
              AND p.client_id = %s
              AND (
                p.square_payment_id IS NOT NULL OR p.square_status IS NOT NULL OR
                p.square_last4 IS NOT NULL OR p.square_card_brand IS NOT NULL
              )
              AND p.payment_date BETWEEN %s AND %s
            ORDER BY p.payment_date NULLS LAST, p.payment_id
            """,
            (rn, rn, client_id, start, end)
        )
        adjacent_records.extend(cur.fetchall())

    # Write report
    reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports'))
    os.makedirs(reports_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(reports_dir, f'square_audit_unpaid_charters_{ts}.csv')

    headers = [
        'reserve_number','charter_id','client_id','charter_date',
        'scope','payment_id','payment_date','amount','payment_method',
        'payment_reserve','square_payment_id','square_last4','square_card_brand','square_status','notes'
    ]

    # Index direct rows by reserve for quick lookup
    direct_by_rn = {}
    for d in direct_rows:
        rn_d, pid, pdate, method, amount, spid, last4, brand, status, notes = d
        direct_by_rn.setdefault(rn_d, []).append({
            'reserve_number': rn_d,
            'charter_id': charter_info.get(rn_d, {}).get('charter_id'),
            'client_id': charter_info.get(rn_d, {}).get('client_id'),
            'charter_date': charter_info.get(rn_d, {}).get('charter_date'),
            'scope': 'direct',
            'payment_id': pid,
            'payment_date': pdate,
            'amount': amount,
            'payment_method': method,
            'payment_reserve': rn_d,
            'square_payment_id': spid,
            'square_last4': last4,
            'square_card_brand': brand,
            'square_status': status,
            'notes': notes,
        })

    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        # Direct rows first
        for rn in reserves:
            for row in direct_by_rn.get(rn, []):
                w.writerow(row)
        # Adjacent rows next
        for rec in adjacent_records:
            rn, cid, client_id, cdate, pid, pdate, amount, pay_rn, method, spid, last4, brand, status, notes = rec
            w.writerow({
                'reserve_number': rn,
                'charter_id': cid,
                'client_id': client_id,
                'charter_date': cdate,
                'scope': 'adjacent',
                'payment_id': pid,
                'payment_date': pdate,
                'amount': amount,
                'payment_method': method,
                'payment_reserve': pay_rn,
                'square_payment_id': spid,
                'square_last4': last4,
                'square_card_brand': brand,
                'square_status': status,
                'notes': notes,
            })

    # Print simple summary
    direct_count = sum(len(v) for v in direct_by_rn.values())
    adjacent_count = len(adjacent_records)
    print(f"Square audit written: {out_path}")
    print(f"Direct Square payments linked to listed reserves: {direct_count}")
    print(f"Adjacent Square payments (same client, +/- {args.window_days}d): {adjacent_count}")

    cur.close(); conn.close()


if __name__ == '__main__':
    main()
