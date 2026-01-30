#!/usr/bin/env python3
"""
Compare charter 019404 between LMS and PostgreSQL.
"""

import pyodbc
import psycopg2
from psycopg2.extras import RealDictCursor

LMS_PATH = r'L:\limo\backups\lms.mdb'

# LMS connection
lms_conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
lms_cur = lms_conn.cursor()

# PostgreSQL connection
pg_conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
pg_cur = pg_conn.cursor(cursor_factory=RealDictCursor)

print("=" * 80)
print("CHARTER 019404: LMS vs PostgreSQL COMPARISON")
print("=" * 80)

# LMS Reserve data
print("\n📋 LMS RESERVE 019404:")
lms_cur.execute("""
    SELECT Reserve_No, Est_Charge, Deposit, Balance, Cancelled
    FROM Reserve
    WHERE Reserve_No = '019404'
""")
lms_reserve = lms_cur.fetchone()

if lms_reserve:
    print(f"   Reserve: {lms_reserve[0]}")
    print(f"   Est_Charge (total): ${lms_reserve[1] or 0:.2f}")
    print(f"   Deposit (paid): ${lms_reserve[2] or 0:.2f}")
    print(f"   Balance: ${lms_reserve[3] or 0:.2f}")
    print(f"   Cancelled: {lms_reserve[4]}")
else:
    print("   NOT FOUND IN LMS")

# LMS Payments
print("\n💰 LMS PAYMENTS FOR 019404:")
lms_cur.execute("""
    SELECT PaymentID, Amount, LastUpdated
    FROM Payment
    WHERE Reserve_No = '019404'
    ORDER BY LastUpdated
""")
lms_payments = lms_cur.fetchall()

lms_total = 0
for p in lms_payments:
    print(f"   Payment {p[0]}: ${p[1]:.2f} on {p[2]}")
    lms_total += p[1]
print(f"   LMS TOTAL: ${lms_total:.2f}")

# PostgreSQL Charter
print("\n📋 POSTGRESQL CHARTER 019404:")
pg_cur.execute("""
    SELECT charter_id, reserve_number, total_amount_due, paid_amount, balance, cancelled
    FROM charters
    WHERE reserve_number = '019404'
""")
pg_charter = pg_cur.fetchone()

if pg_charter:
    print(f"   Charter ID: {pg_charter['charter_id']}")
    print(f"   Total due: ${pg_charter['total_amount_due'] or 0:.2f}")
    print(f"   Paid: ${pg_charter['paid_amount'] or 0:.2f}")
    print(f"   Balance: ${pg_charter['balance'] or 0:.2f}")
    print(f"   Cancelled: {pg_charter['cancelled']}")

# PostgreSQL Payments
print("\n💰 POSTGRESQL PAYMENTS FOR 019404:")
pg_cur.execute("""
    SELECT payment_id, amount, payment_date, payment_method, charter_id
    FROM payments
    WHERE reserve_number = '019404'
    ORDER BY payment_date
""")
pg_payments = pg_cur.fetchall()

pg_total = 0
for p in pg_payments:
    status = "UNLINKED" if p['charter_id'] is None else f"LINKED to {p['charter_id']}"
    print(f"   Payment {p['payment_id']}: ${p['amount']:.2f} on {p['payment_date']}, {status}")
    pg_total += p['amount']
print(f"   POSTGRESQL TOTAL: ${pg_total:.2f}")

# Comparison
print("\n" + "=" * 80)
print("🔍 COMPARISON:")
print("=" * 80)

if lms_reserve:
    print(f"   LMS Est_Charge: ${lms_reserve[1] or 0:.2f}")
    print(f"   PG Total due:   ${pg_charter['total_amount_due'] or 0:.2f}")
    print(f"   Difference:     ${(pg_charter['total_amount_due'] or 0) - (lms_reserve[1] or 0):.2f}")
    
    print(f"\n   LMS Deposit:    ${lms_reserve[2] or 0:.2f}")
    print(f"   PG Paid:        ${pg_charter['paid_amount'] or 0:.2f}")
    print(f"   Difference:     ${(pg_charter['paid_amount'] or 0) - (lms_reserve[2] or 0):.2f}")
    
    print(f"\n   LMS Balance:    ${lms_reserve[3] or 0:.2f}")
    print(f"   PG Balance:     ${pg_charter['balance'] or 0:.2f}")
    print(f"   Difference:     ${(pg_charter['balance'] or 0) - (lms_reserve[3] or 0):.2f}")

print("\n" + "=" * 80)
print("[FAIL] CONCLUSION:")
print("=" * 80)

if lms_reserve and abs((pg_charter['paid_amount'] or 0) - (lms_reserve[2] or 0)) > 0.01:
    extra = (pg_charter['paid_amount'] or 0) - (lms_reserve[2] or 0)
    print(f"   PostgreSQL has ${extra:.2f} EXTRA in payments")
    print(f"   These {len(pg_payments)} payments with reserve 019404 don't all belong here!")
    print(f"   Need to identify which payments are incorrectly tagged with this reserve#")

lms_cur.close()
pg_cur.close()
lms_conn.close()
pg_conn.close()

print("\n" + "=" * 80)
print("✓ Comparison complete")
print("=" * 80)
