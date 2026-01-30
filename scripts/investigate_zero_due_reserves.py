#!/usr/bin/env python3
"""Investigate the 2 reserves with $0 total_due."""

import psycopg2
import pyodbc

pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
pg_cur = pg_conn.cursor()

lms_conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ=L:\\limo\\backups\\lms.mdb;')
lms_cur = lms_conn.cursor()

for reserve in ['015279', '015542']:
    print(f"Reserve {reserve}:")
    
    # PG charter
    pg_cur.execute("""
        SELECT charter_date, cancelled, total_amount_due, paid_amount, balance
        FROM charters WHERE reserve_number = %s
    """, (reserve,))
    pg_data = pg_cur.fetchone()
    print(f"  PG: date={pg_data[0]}, cancelled={pg_data[1]}, due=${pg_data[2]}, paid=${pg_data[3]}, balance=${pg_data[4]}")
    
    # LMS
    lms_cur.execute("SELECT Est_Charge, Deposit, Balance FROM Reserve WHERE Reserve_No = ?", (reserve,))
    lms_data = lms_cur.fetchone()
    if lms_data:
        print(f"  LMS: due=${lms_data[0]}, paid=${lms_data[1]}, balance=${lms_data[2]}")
    else:
        print(f"  LMS: NOT FOUND")
    
    # PG payments
    pg_cur.execute("""
        SELECT payment_id, amount, payment_date, payment_key
        FROM payments WHERE reserve_number = %s
        ORDER BY payment_date
    """, (reserve,))
    payments = pg_cur.fetchall()
    print(f"  Payments: {len(payments)}")
    for pid, amt, pdate, pkey in payments:
        print(f"    {pid}: ${amt:.2f} on {pdate} (key={pkey})")
    
    print()

pg_cur.close()
pg_conn.close()
lms_cur.close()
lms_conn.close()
