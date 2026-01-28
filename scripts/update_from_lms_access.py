#!/usr/bin/env python3
"""
Incremental update from LMS Access DB to PostgreSQL.
- Only updates rows in charters, payments, clients, vehicles that are new or amended.
- Logs all changes to reports/lms_access_update_log.csv
"""
import os
import csv
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

PG_HOST = os.getenv('DB_HOST','localhost')
load_dotenv('L:/limo/.env')
PG_PORT = int(os.getenv('DB_PORT','5432'))
PG_NAME = os.getenv('DB_NAME','almsdata')
PG_USER = os.getenv('DB_USER','postgres')
PG_PASSWORD = os.getenv('DB_PASSWORD','')
LOG_CSV = r'l:/limo/reports/lms_access_update_log.csv'


# Field mappings for charters, clients, payments
CHARTERS_FIELDS = ['reserve_no', 'last_updated', 'raw_data']
CLIENTS_FIELDS = ['customer_id', 'last_updated', 'raw_data']
PAYMENTS_FIELDS = ['payment_id', 'reserve_no', 'last_updated', 'raw_data']

def main():
    os.makedirs(os.path.dirname(LOG_CSV), exist_ok=True)
    updated = []
    print(f"DB_HOST={PG_HOST} DB_PORT={PG_PORT} DB_NAME={PG_NAME} DB_USER={PG_USER} DB_PASSWORD={'***' if PG_PASSWORD else '(empty)'}")
    with psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_NAME, user=PG_USER, password=PG_PASSWORD) as pg_conn:
        pg_conn.autocommit = True
        with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
            # --- Clients FIRST ---
            cur.execute("SELECT customer_id, last_updated, raw_data FROM lms_staging_customer")
            staging_clients = {r['customer_id']: r for r in cur.fetchall()}
            cur.execute("SELECT client_id, account_number, company_name, client_name, email, address_line1, city, zip_code FROM clients")
            clients_by_id = {r['client_id']: r for r in cur.fetchall()}
            clients_by_acc = {r['account_number']: r for r in clients_by_id.values() if r['account_number']}
            for _, srow in staging_clients.items():
                raw = srow['raw_data']
                client_data = raw if isinstance(raw, dict) else json.loads(raw)
                account_number = client_data.get('Account_No')
                if not account_number:
                    continue
                account_number = str(account_number)
                company_name = client_data.get('CompanyName') or None
                client_name = client_data.get('Name') or None
                email = client_data.get('EMail') or None
                address_line1 = client_data.get('Line_1') or None
                city = client_data.get('City') or None
                zip_code = client_data.get('Zip_Code') or None
                existing = clients_by_acc.get(account_number)
                if not existing:
                    # No insert here; log and continue (keeps updater idempotent and avoids unintended client creation)
                    updated.append({'action':'skip','table':'clients','client_id':None,'fields':{'reason':'no existing client for account_number','account_number':account_number}})
                    continue
                changes = {}
                if existing.get('company_name') != company_name and company_name is not None:
                    changes['company_name'] = company_name
                if existing.get('client_name') != client_name and client_name is not None:
                    changes['client_name'] = client_name
                if existing.get('email') != email and email is not None:
                    changes['email'] = email
                if existing.get('address_line1') != address_line1 and address_line1 is not None:
                    changes['address_line1'] = address_line1
                if existing.get('city') != city and city is not None:
                    changes['city'] = city
                if existing.get('zip_code') != zip_code and zip_code is not None:
                    changes['zip_code'] = zip_code
                if changes:
                    sets = ','.join(f"{k}=%s" for k in changes)
                    vals = [changes[k] for k in changes]
                    cur.execute(f"UPDATE clients SET {sets} WHERE client_id=%s", vals + [existing['client_id']])
                    updated.append({'action':'update','table':'clients','client_id':existing['client_id'],'fields':changes})
                    # keep cache in sync
                    clients_by_id[existing['client_id']].update(changes)
                    clients_by_acc[account_number].update(changes)

            # --- Charters ---
            cur.execute("SELECT reserve_no, last_updated, raw_data FROM lms_staging_reserve")
            staging_reserves = {r['reserve_no']: r for r in cur.fetchall()}
            cur.execute("SELECT reserve_number, charter_id, client_id, payment_status FROM charters")
            prod_charters = {r['reserve_number']: r for r in cur.fetchall()}
            for reserve_no, srow in staging_reserves.items():
                raw = srow['raw_data']
                # Map fields from raw_data
                if isinstance(raw, dict):
                    charter_data = raw
                else:
                    charter_data = json.loads(raw)
                account_number = charter_data.get('Account_No')
                client_id = None
                if account_number:
                    account_number = str(account_number)
                    existing = clients_by_acc.get(account_number)
                    if existing:
                        client_id = existing['client_id']
                payment_status = charter_data.get('Status') or None
                # If we can't resolve a client_id, skip to avoid FK violations
                if client_id is None:
                    updated.append({'action':'skip','table':'charters','reserve_number':reserve_no,'fields':{'reason':'no client found for account_number','account_number':account_number}})
                    continue
                # Insert new charter if not present
                if reserve_no not in prod_charters:
                    cur.execute(
                        "INSERT INTO charters (reserve_number, client_id, payment_status) VALUES (%s,%s,%s)",
                        [reserve_no, client_id, payment_status]
                    )
                    updated.append({'action':'insert','table':'charters','reserve_number':reserve_no,'fields':{'client_id':client_id,'payment_status':payment_status}})
                else:
                    # Update if changed
                    prod = prod_charters[reserve_no]
                    changes = {}
                    if prod['client_id'] != client_id:
                        changes['client_id'] = client_id
                    if prod['payment_status'] != payment_status:
                        changes['payment_status'] = payment_status
                    if changes:
                        sets = ','.join(f'{k}=%s' for k in changes)
                        vals = [changes[k] for k in changes]
                        cur.execute(f"UPDATE charters SET {sets} WHERE reserve_number=%s", vals+[reserve_no])
                        updated.append({'action':'update','table':'charters','reserve_number':reserve_no,'fields':changes})
            # --- Payments ---
            cur.execute("SELECT payment_id, reserve_no, last_updated, raw_data FROM lms_staging_payment")
            staging_payments = {r['payment_id']: r for r in cur.fetchall()}
            cur.execute("SELECT payment_id, reserve_number, amount, payment_date FROM payments")
            prod_payments = {r['payment_id']: r for r in cur.fetchall()}
            for payment_id, srow in staging_payments.items():
                raw = srow['raw_data']
                if isinstance(raw, dict):
                    pay_data = raw
                else:
                    pay_data = json.loads(raw)
                reserve_number = pay_data.get('Reserve_No') or None
                amount = pay_data.get('Amount') or None
                payment_date = pay_data.get('LastUpdated') or None
                # Insert new payment if not present
                if payment_id not in prod_payments:
                    cur.execute(
                        "INSERT INTO payments (payment_id, reserve_number, amount, payment_date) VALUES (%s,%s,%s,%s)",
                        [payment_id, reserve_number, amount, payment_date]
                    )
                    updated.append({'action':'insert','table':'payments','payment_id':payment_id,'fields':{'reserve_number':reserve_number,'amount':amount,'payment_date':payment_date}})
                else:
                    prod = prod_payments[payment_id]
                    changes = {}
                    if prod['reserve_number'] != reserve_number:
                        changes['reserve_number'] = reserve_number
                    if prod['amount'] != amount:
                        changes['amount'] = amount
                    if prod['payment_date'] != payment_date:
                        changes['payment_date'] = payment_date
                    if changes:
                        sets = ','.join(f'{k}=%s' for k in changes)
                        vals = [changes[k] for k in changes]
                        cur.execute(f"UPDATE payments SET {sets} WHERE payment_id=%s", vals+[payment_id])
                        updated.append({'action':'update','table':'payments','payment_id':payment_id,'fields':changes})
    # Log changes
    with open(LOG_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['action','table','id','fields'])
        w.writeheader()
        for r in updated:
            # Use id field for charter/client/payment
            id_field = r.get('charter_id') or r.get('reserve_number') or r.get('client_id') or r.get('payment_id')
            w.writerow({'action':r['action'],'table':r['table'],'id':id_field,'fields':json.dumps(r['fields'])})
    print('Update log written to', LOG_CSV)

if __name__ == '__main__':
    main()
