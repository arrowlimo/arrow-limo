#!/usr/bin/env python3
"""Apply fixes based on residual_overpaid_analysis.csv.
Actions:
  increase_due_to_charge_sum -> set total_amount_due = charge_sum
  increase_due_to_LMS        -> set total_amount_due = lms_est_charge
  delete_extra_payments      -> delete payments beyond LMS count (NULL-key or ETR first)
  credit_or_adjust_due       -> if excess <=5 create rounding credit
  review                     -> skip
Dry-run unless --write.
"""
import csv, psycopg2, pyodbc, datetime
from decimal import Decimal
from argparse import ArgumentParser

PG = dict(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
LMS_PATH = r'L:\\limo\\backups\\lms.mdb'
FILE = 'residual_overpaid_analysis.csv'


def load_rows():
    rows=[]
    with open(FILE,'r',encoding='utf-8') as f:
        r=csv.DictReader(f)
        for row in r:
            rows.append(row)
    return rows


def backup(cur):
    ts=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    name=f'charters_backup_residual_{ts}'
    cur.execute(f'CREATE TABLE {name} AS SELECT * FROM charters')
    return name


def main():
    ap=ArgumentParser(description='Apply residual overpaid fixes')
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()

    rows=load_rows()
    pg=psycopg2.connect(**PG); cur=pg.cursor()
    lms=pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'); lcur=lms.cursor()

    pending=[]
    for row in rows:
        action=row['recommended_action']
        reserve=row['reserve_number']
        excess=Decimal(row['excess'])
        if action=='review':
            continue
        pending.append((reserve, action, excess, row))

    if not args.write:
        for p in pending:
            print(f"DRY-RUN {p[0]} -> {p[1]} excess {p[2]:.2f}")
        print(f'Total actionable: {len(pending)}')
        cur.close(); pg.close(); lcur.close(); lms.close(); return

    b=backup(cur); print('Backup created:', b)
    applied=0

    for reserve, action, excess, row in pending:
        # Fetch charter id
        cur.execute('SELECT charter_id, total_amount_due, paid_amount, client_id FROM charters WHERE reserve_number=%s', (reserve,))
        c=cur.fetchone()
        if not c: continue
        charter_id, due, paid, client_id=c
        pg_excess=paid - due
        if pg_excess<=0: continue

        if action=='increase_due_to_charge_sum':
            new_due=Decimal(row['charge_sum'])
            cur.execute('UPDATE charters SET total_amount_due=%s, balance=%s - paid_amount WHERE charter_id=%s', (new_due, new_due, charter_id))
            applied+=1
        elif action=='increase_due_to_LMS':
            new_due=Decimal(row['lms_est_charge'])
            cur.execute('UPDATE charters SET total_amount_due=%s, balance=%s - paid_amount WHERE charter_id=%s', (new_due, new_due, charter_id))
            applied+=1
        elif action=='delete_extra_payments':
            # compare counts
            lcur.execute('SELECT COUNT(*) FROM Payment WHERE Reserve_No=?', reserve)
            lms_count=lcur.fetchone()[0]
            cur.execute('SELECT payment_id, payment_key, created_at FROM payments WHERE reserve_number=%s ORDER BY payment_date', (reserve,))
            pg_pay=cur.fetchall()
            if len(pg_pay)<=lms_count: continue
            extras=pg_pay[lms_count:]
            deletable=[pid for pid,key,created in extras if key is None or (key and key.startswith('ETR:'))]
            if deletable:
                cur.execute('DELETE FROM income_ledger WHERE payment_id = ANY(%s)', (deletable,))
                cur.execute('DELETE FROM banking_payment_links WHERE payment_id = ANY(%s)', (deletable,))
                cur.execute('DELETE FROM payments WHERE payment_id = ANY(%s)', (deletable,))
                # recalc charter
                cur.execute('WITH s AS (SELECT COALESCE(SUM(amount),0) t FROM payments WHERE reserve_number=%s) UPDATE charters SET paid_amount=(SELECT t FROM s), balance=total_amount_due-(SELECT t FROM s) WHERE charter_id=%s', (reserve, charter_id))
                applied+=1
        elif action=='credit_or_adjust_due':
            # create rounding credit
            cur.execute("""
                INSERT INTO charter_credit_ledger
                  (source_reserve_number, source_charter_id, client_id, credit_amount, remaining_balance, credit_reason, created_date, notes, created_by)
                VALUES (%s,%s,%s,%s,%s,%s, CURRENT_TIMESTAMP, %s,%s)
            """, (reserve, charter_id, client_id, pg_excess, pg_excess, 'ROUNDING_SMALL', 'Small rounding excess', 'system'))
            cur.execute('UPDATE charters SET paid_amount=paid_amount - %s, balance=total_amount_due - (paid_amount - %s) WHERE charter_id=%s', (pg_excess, pg_excess, charter_id))
            applied+=1

    pg.commit(); print(f'Applied fixes to {applied} charters')

    lcur.close(); lms.close(); cur.close(); pg.close()

if __name__=='__main__':
    main()
