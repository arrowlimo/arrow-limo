#!/usr/bin/env python3
"""Apply deletions for overpaid charters classified as duplicates.

Reads: duplicates_deletions.csv and zero_due_duplicates.csv
Deletes suspect duplicate payments: criteria
  - payment_key IS NULL OR payment_key LIKE 'ETR:%'
  - created_at::date = '2025-08-05' OR (amount > total_amount_due and charter already satisfied)
Keeps at least LMS payment count.

Dry-run by default; use --write to apply.
"""
import csv, psycopg2, pyodbc, datetime
from decimal import Decimal
from argparse import ArgumentParser

PG = dict(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
LMS_PATH = r'L:\\limo\\backups\\lms.mdb'

DUP_FILES = ['duplicates_deletions.csv','zero_due_duplicates.csv']


def load_targets():
    targets = set()
    for fn in DUP_FILES:
        try:
            with open(fn,'r',encoding='utf-8') as f:
                r = csv.DictReader(f)
                for row in r:
                    targets.add(row['reserve_number'])
        except FileNotFoundError:
            pass
    return sorted(targets)


def lms_payment_count(lms_cur, reserve):
    lms_cur.execute('SELECT COUNT(*) FROM Payment WHERE Reserve_No=?', reserve)
    return lms_cur.fetchone()[0]


def fetch_pg_payments(pg_cur, reserve):
    pg_cur.execute("SELECT payment_id, amount, payment_key, payment_date, created_at FROM payments WHERE reserve_number=%s ORDER BY payment_date", (reserve,))
    return pg_cur.fetchall()


def delete_payments(pg_cur, payment_ids):
    if not payment_ids:
        return (0,0,0)
    # FK cascades
    pg_cur.execute("DELETE FROM income_ledger WHERE payment_id = ANY(%s)", (payment_ids,))
    il = pg_cur.rowcount
    pg_cur.execute("DELETE FROM banking_payment_links WHERE payment_id = ANY(%s)", (payment_ids,))
    bl = pg_cur.rowcount
    pg_cur.execute("DELETE FROM payments WHERE payment_id = ANY(%s)", (payment_ids,))
    pm = pg_cur.rowcount
    return il, bl, pm


def recalc_charter(pg_cur, reserve):
    pg_cur.execute("""
        WITH payment_sum AS (SELECT COALESCE(SUM(amount),0) AS total FROM payments WHERE reserve_number=%s)
        UPDATE charters SET paid_amount=(SELECT total FROM payment_sum), balance=total_amount_due-(SELECT total FROM payment_sum)
        WHERE reserve_number=%s
    """, (reserve, reserve))


def main():
    ap = ArgumentParser(description='Delete duplicate payments for overpaid charters')
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    targets = load_targets()
    if not targets:
        print('No target reserves found; ensure remediation CSVs exist.')
        return
    print(f'Target reserves (possible duplicates): {len(targets)}')

    pg = psycopg2.connect(**PG); pg_cur = pg.cursor()
    lms = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'); lms_cur = lms.cursor()

    total_deleted = 0
    change_log = []

    for reserve in targets:
        lms_count = lms_payment_count(lms_cur, reserve)
        pg_pay = fetch_pg_payments(pg_cur, reserve)
        pg_count = len(pg_pay)
        if pg_count <= lms_count:
            continue  # nothing extra
        # Choose deletable: extras beyond first lms_count, preferring NULL-key and 2025-08-05 created
        to_consider = pg_pay[lms_count:]  # extras
        deletable = []
        for pid, amount, key, pdate, created in to_consider:
            if key is None or (key and key.startswith('ETR:')) or (created.date() == datetime.date(2025,8,5)):
                deletable.append(pid)
        if not deletable:
            continue
        if args.write:
            il, bl, pm = delete_payments(pg_cur, deletable)
            recalc_charter(pg_cur, reserve)
            total_deleted += pm
            change_log.append((reserve, pm, il, bl))
        else:
            print(f'DRY-RUN reserve {reserve}: would delete {len(deletable)} of {pg_count - lms_count} extras')

    if args.write:
        pg.commit()
        print(f'✓ Deleted {total_deleted} payments across {len(change_log)} reserves')
    else:
        print('No changes applied (dry-run).')

    lms_cur.close(); lms.close(); pg_cur.close(); pg.close()

if __name__ == '__main__':
    main()
