#!/usr/bin/env python3
"""Apply provisional credits for NEED_MANUAL category.

Reads manual_review.csv. For each reserve still overpaid after prior fixes, moves excess into credit ledger with reason MANUAL_REVIEW.
Skips if excess <=0 now.
Dry-run unless --write passed.
"""
import csv, psycopg2, datetime
from decimal import Decimal
from argparse import ArgumentParser

PG = dict(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
MANUAL_FILE = 'manual_review.csv'


def load_manual():
    rows = []
    with open(MANUAL_FILE,'r',encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row['reserve_number'])
    return rows


def create_backup(cur):
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    name = f'charters_backup_manual_{ts}'
    cur.execute(f'CREATE TABLE {name} AS SELECT * FROM charters')
    return name


def main():
    ap = ArgumentParser(description='Apply provisional manual review credits')
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    reserves = load_manual()
    print(f'Manual review reserves: {len(reserves)}')

    pg = psycopg2.connect(**PG); cur = pg.cursor()

    to_apply = []
    for reserve in reserves:
        cur.execute('SELECT charter_id, client_id, total_amount_due, paid_amount FROM charters WHERE reserve_number=%s', (reserve,))
        c = cur.fetchone()
        if not c:
            continue
        charter_id, client_id, due, paid = c
        excess = paid - due
        if excess > 0:
            to_apply.append((reserve, charter_id, client_id, excess))

    if not args.write:
        for r, cid, clid, ex in to_apply[:20]:
            print(f'DRY-RUN first20: {r} excess {ex:.2f}')
        print(f'Total to apply: {len(to_apply)} credits')
        cur.close(); pg.close(); return

    backup = create_backup(cur)
    print(f'Backup created: {backup}')

    applied = 0
    for reserve, charter_id, client_id, excess in to_apply:
        cur.execute("""
            INSERT INTO charter_credit_ledger
              (source_reserve_number, source_charter_id, client_id, credit_amount, remaining_balance, credit_reason, created_date, notes, created_by)
            VALUES (%s,%s,%s,%s,%s,%s, CURRENT_TIMESTAMP, %s,%s)
        """, (reserve, charter_id, client_id, excess, excess, 'MANUAL_REVIEW', 'Provisional manual credit', 'system'))
        cur.execute('UPDATE charters SET paid_amount = paid_amount - %s, balance = total_amount_due - (paid_amount - %s) WHERE charter_id=%s', (excess, excess, charter_id))
        applied += 1
    pg.commit()
    print(f'✓ Applied {applied} provisional manual credits')

    cur.close(); pg.close()

if __name__ == '__main__':
    main()
