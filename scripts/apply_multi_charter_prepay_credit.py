#!/usr/bin/env python3
"""Apply multi-charter prepay credit for Fink Shannon (reserve 017631).

Excess = paid_amount - total_amount_due.
Creates credit ledger entry with reason MULTI_CHARTER_PREPAY and reduces charter.paid_amount by excess.

Dry-run unless --write provided.
"""
import psycopg2, datetime
from decimal import Decimal
from argparse import ArgumentParser

PG = dict(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
TARGET_RESERVE = '017631'


def main():
    ap = ArgumentParser(description='Apply multi-charter prepay credit for Fink Shannon reserve 017631')
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    pg = psycopg2.connect(**PG); cur = pg.cursor()
    cur.execute('SELECT charter_id, client_id, total_amount_due, paid_amount FROM charters WHERE reserve_number=%s', (TARGET_RESERVE,))
    row = cur.fetchone()
    if not row:
        print('Target charter not found.')
        return
    charter_id, client_id, due, paid = row
    excess = paid - due
    if excess <= 0:
        print('No excess remaining; nothing to apply.')
        return
    print(f'Reserve {TARGET_RESERVE}: due={due:.2f} paid={paid:.2f} excess={excess:.2f}')

    if not args.write:
        print('DRY-RUN: Would create credit ledger entry and reduce paid_amount to due.')
        cur.close(); pg.close(); return

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = f'charters_backup_fink_{ts}'
    # reserve_number is text; quote literal safely
    cur.execute(f"CREATE TABLE {backup} AS SELECT * FROM charters WHERE reserve_number='{TARGET_RESERVE}'")

    cur.execute("""
        INSERT INTO charter_credit_ledger
          (source_reserve_number, source_charter_id, client_id, credit_amount, remaining_balance, credit_reason, created_date, notes, created_by)
        VALUES (%s,%s,%s,%s,%s,%s, CURRENT_TIMESTAMP, %s, %s)
    """, (TARGET_RESERVE, charter_id, client_id, excess, excess, 'MULTI_CHARTER_PREPAY', 'Multi-charter prepay excess captured', 'system'))

    cur.execute("UPDATE charters SET paid_amount = %s, balance = total_amount_due - %s WHERE charter_id=%s", (due, due, charter_id))

    pg.commit()
    print(f'✓ Applied multi-charter prepay credit {excess:.2f} for reserve {TARGET_RESERVE}')

    cur.close(); pg.close()

if __name__ == '__main__':
    main()
