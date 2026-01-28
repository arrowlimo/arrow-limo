#!/usr/bin/env python3
"""Check 019209 payments in PostgreSQL and compare to LMS."""

import psycopg2
import pyodbc
import os

# PostgreSQL
pg_conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
pg_cur = pg_conn.cursor()

print("\n" + "="*80)
print("CHARTER 019209 - POSTGRESQL PAYMENTS")
print("="*80)

pg_cur.execute("""
    SELECT payment_date, amount, payment_method, payment_key, notes
    FROM payments
    WHERE reserve_number = '019209'
    ORDER BY payment_date
""")

pg_payments = pg_cur.fetchall()
if pg_payments:
    total = 0
    for pdate, amt, method, key, notes in pg_payments:
        print(f"  {pdate} ${amt:>10.2f} {method:<15} Key:{key} Notes:{notes}")
        total += float(amt)
    print(f"  TOTAL: ${total:.2f}")
else:
    print("  No payments found in PostgreSQL")

# LMS
LMS_PATH = r'L:\limo\backups\lms.mdb'
conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
lms_conn = pyodbc.connect(conn_str)
lms_cur = lms_conn.cursor()

print("\n" + "="*80)
print("CHARTER 019209 - LMS PAYMENTS")
print("="*80)

lms_cur.execute("""
    SELECT [Key], LastUpdated, Amount, LastUpdatedBy
    FROM Payment
    WHERE Reserve_No = '019209'
    ORDER BY LastUpdated
""")

lms_payments = lms_cur.fetchall()
if lms_payments:
    total = 0
    for key, date, amt, by_who in lms_payments:
        print(f"  {key:<20} {date} ${amt or 0:>10.2f} by {by_who}")
        total += (amt or 0)
    print(f"  TOTAL PAID: ${total:.2f}")
else:
    print("  No payments found in LMS")

print("\n" + "="*80)
print("COMPARISON")
print("="*80)

pg_total = sum([float(p[1]) for p in pg_payments]) if pg_payments else 0
lms_total = sum([p[2] or 0 for p in lms_payments]) if lms_payments else 0

print(f"PostgreSQL Total: ${pg_total:.2f}")
print(f"LMS Total: ${lms_total:.2f}")
print(f"Difference: ${pg_total - lms_total:.2f}")

if abs(pg_total - lms_total) > 0.01:
    print("\nACTION NEEDED: Import missing payments from LMS to PostgreSQL")
    print(f"Missing amount: ${lms_total - pg_total:.2f}")

pg_cur.close()
pg_conn.close()
lms_cur.close()
lms_conn.close()

print("\n")
