#!/usr/bin/env python3
"""Investigate Fink Shannon overpayment details (PG vs LMS)."""
import psycopg2, pyodbc, os

PG_DSN = dict(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
LMS_PATH = r'L:\limo\backups\lms.mdb'

def main():
    pg = psycopg2.connect(**PG_DSN)
    pc = pg.cursor()
    pc.execute("""
        SELECT c.reserve_number, c.charter_date, c.total_amount_due, c.paid_amount, c.balance, cl.client_name
        FROM charters c JOIN clients cl ON cl.client_id=c.client_id
        WHERE cl.client_name ILIKE '%Fink Shannon%'
        AND c.paid_amount > c.total_amount_due
        ORDER BY c.charter_date
    """)
    rows = pc.fetchall()
    if not rows:
        print('No overpaid charter found for Fink Shannon')
        return
    print(f"Found {len(rows)} overpaid charter(s) for Fink Shannon")

    lms = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
    lc = lms.cursor()

    for reserve_number, charter_date, due, paid, balance, client in rows:
        print('\nReserve', reserve_number, 'date', charter_date, 'PG due', due, 'paid', paid, 'balance', balance)
        # LMS reserve
        lc.execute('SELECT Est_Charge, Deposit, Balance FROM Reserve WHERE Reserve_No=?', reserve_number)
        lms_res = lc.fetchone()
        print(' LMS Reserve row:', lms_res)
        # LMS payments
        lc.execute('SELECT PaymentID, Amount, LastUpdated FROM Payment WHERE Reserve_No=? ORDER BY LastUpdated', reserve_number)
        lms_payments = lc.fetchall()
        print(' LMS Payments:', lms_payments)
        # PG payments
        pc.execute('SELECT payment_id, amount, payment_key, payment_date, created_at FROM payments WHERE reserve_number=%s ORDER BY payment_date', (reserve_number,))
        pg_payments = pc.fetchall()
        print(' PG Payments:', pg_payments)

    lc.close(); lms.close(); pc.close(); pg.close()

if __name__ == '__main__':
    main()
