#!/usr/bin/env python3
"""Apply credit ledger entries for CANCELLED_DEPOSIT category.

Reads cancelled_deposit_credits.csv
For each reserve:
  credit_amount = excess
  charter.paid_amount -= excess; balance = 0 (since due already satisfied)
Creates backup of charters before modification.

Dry-run unless --write passed.
"""
import csv, psycopg2, datetime
from decimal import Decimal
from argparse import ArgumentParser

PG = dict(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
CANCEL_FILE = 'cancelled_deposit_credits.csv'

def load_rows():
    rows = []
    with open(CANCEL_FILE,'r',encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            excess = Decimal(row['excess'])
            rows.append((row['reserve_number'], row['client_name'], excess))
    return rows

def create_backup(cur):
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = f'charters_backup_cancelled_{ts}'
    cur.execute(f'CREATE TABLE {backup} AS SELECT * FROM charters')
    return backup

def main():
    ap = ArgumentParser(description='Apply cancelled deposit credits')
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    rows = load_rows()
    print(f'Processing {len(rows)} CANCELLED_DEPOSIT reserves')

    pg = psycopg2.connect(**PG); cur = pg.cursor()

    applied = []
    for reserve, client, excess in rows:
        # Fetch charter
        cur.execute('SELECT charter_id, total_amount_due, paid_amount, balance, client_id FROM charters WHERE reserve_number=%s', (reserve,))
        c = cur.fetchone()
        if not c:
            print(f'  SKIP {reserve} (not found)')
            continue
        charter_id, due, paid, bal, client_id = c
        if paid <= due:
            print(f'  SKIP {reserve} (no excess now)')
            continue
        this_excess = paid - due
        # Only apply if matches expected or expected >= actual
        if this_excess <= 0:
            print(f'  SKIP {reserve} (no computed excess)')
            continue
        applied.append((reserve, charter_id, client_id, this_excess))

    if not args.write:
        for a in applied:
            print(f'DRY-RUN credit {a[0]} excess {a[3]:.2f}')
        print('Use --write to apply.')
        cur.close(); pg.close(); return

    backup = create_backup(cur)
    print(f'Created backup table {backup}')

    for reserve, charter_id, client_id, excess in applied:
        # Insert credit ledger
        cur.execute("""
            INSERT INTO charter_credit_ledger
              (source_reserve_number, source_charter_id, client_id, credit_amount, remaining_balance, credit_reason, created_date, notes, created_by)
            VALUES (%s,%s,%s,%s,%s,%s, CURRENT_TIMESTAMP, %s, %s)
        """, (reserve, charter_id, client_id, excess, excess, 'CANCELLED_DEPOSIT', 'Auto credit conversion', 'system'))
        # Adjust charter
        cur.execute("""
            UPDATE charters SET paid_amount = paid_amount - %s, balance = total_amount_due - (paid_amount - %s)
            WHERE charter_id=%s
        """, (excess, excess, charter_id))
        print(f'Applied credit for {reserve}: {excess:.2f}')

    pg.commit()
    print(f'✓ Applied {len(applied)} cancelled deposit credits')

    cur.close(); pg.close()

if __name__ == '__main__':
    main()
