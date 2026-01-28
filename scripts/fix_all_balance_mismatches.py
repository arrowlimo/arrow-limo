#!/usr/bin/env python3
"""
Fix all charter balance mismatches by importing missing payments from LMS.
Fixes: 019727, 016086, 015940, 015808, 013690, 017991, 017720, 018199
"""

import psycopg2
import pyodbc
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def get_lms_connection():
    LMS_PATH = r'L:\limo\backups\lms.mdb'
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

problem_charters = [
    '019727',  # Missing $500 in payments
    '016086',  # Missing $1,486.70 in payments
    '013690',  # Missing $1,240 in payments
    '017991',  # Has $200 extra payment in PG (should have $0)
    '017720',  # Missing $1,020 in payments
    '018199',  # Missing $1,000 in payments
    '015940',  # Cancelled - should have $0 total
    '015808',  # Cancelled - should have $0 total
]

lms_conn = get_lms_connection()
lms_cur = lms_conn.cursor()

pg_conn = get_db_connection()
pg_cur = pg_conn.cursor()

print("\n" + "="*100)
print("FIXING CHARTER BALANCE MISMATCHES")
print("="*100)

total_imported = 0
total_fixed = 0

for reserve_num in problem_charters:
    print(f"\n{'='*100}")
    print(f"CHARTER {reserve_num}")
    print(f"{'='*100}")
    
    # Get LMS data
    lms_cur.execute("""
        SELECT Est_Charge, Deposit, Balance
        FROM Reserve
        WHERE Reserve_No = ?
    """, (reserve_num,))
    lms_reserve = lms_cur.fetchone()
    
    if not lms_reserve:
        print(f"  NOT FOUND IN LMS")
        continue
    
    lms_total = float(lms_reserve[0] or 0)
    lms_paid = float(lms_reserve[1] or 0)
    lms_balance = float(lms_reserve[2] or 0)
    
    # Get PostgreSQL data
    pg_cur.execute("""
        SELECT total_amount_due, paid_amount, balance
        FROM charters
        WHERE reserve_number = %s
    """, (reserve_num,))
    pg_charter = pg_cur.fetchone()
    
    if not pg_charter:
        print(f"  NOT FOUND IN POSTGRESQL")
        continue
    
    pg_total = float(pg_charter[0] or 0)
    pg_paid = float(pg_charter[1] or 0)
    pg_balance = float(pg_charter[2] or 0)
    
    print(f"  LMS:        Total=${lms_total:.2f}  Paid=${lms_paid:.2f}  Balance=${lms_balance:.2f}")
    print(f"  PostgreSQL: Total=${pg_total:.2f}  Paid=${pg_paid:.2f}  Balance=${pg_balance:.2f}")
    
    # Get LMS payments
    lms_cur.execute("""
        SELECT PaymentID, [Key], LastUpdated, Amount
        FROM Payment
        WHERE Reserve_No = ?
        ORDER BY LastUpdated
    """, (reserve_num,))
    lms_payments = lms_cur.fetchall()
    
    # Get PostgreSQL payments
    pg_cur.execute("""
        SELECT payment_key
        FROM payments
        WHERE reserve_number = %s
    """, (reserve_num,))
    pg_keys = {row[0] for row in pg_cur.fetchall()}
    
    # Find missing payments
    missing_payments = []
    for payment_id, key, date, amt in lms_payments:
        lms_key = f"LMS:{payment_id}"
        if lms_key not in pg_keys:
            missing_payments.append({
                'payment_id': payment_id,
                'key': key,
                'date': date,
                'amount': float(amt or 0)
            })
    
    if missing_payments:
        missing_total = sum([p['amount'] for p in missing_payments])
        print(f"\n  MISSING {len(missing_payments)} payments totaling ${missing_total:.2f}:")
        for mp in missing_payments:
            print(f"    PaymentID {mp['payment_id']}: ${mp['amount']:.2f} on {mp['date'].date()}")
        
        # Import missing payments
        for mp in missing_payments:
            pg_cur.execute("""
                INSERT INTO payments (
                    reserve_number, amount, payment_date, payment_method,
                    payment_key, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                reserve_num,
                mp['amount'],
                mp['date'].date(),
                'unknown',
                f"LMS:{mp['payment_id']}",
                f"Imported from LMS Payment ID {mp['payment_id']}"
            ))
        
        total_imported += len(missing_payments)
    
    # Recalculate charter balance
    pg_cur.execute("""
        UPDATE charters
        SET paid_amount = (
            SELECT COALESCE(SUM(amount), 0)
            FROM payments
            WHERE reserve_number = %s
        ),
        balance = total_amount_due - (
            SELECT COALESCE(SUM(amount), 0)
            FROM payments
            WHERE reserve_number = %s
        )
        WHERE reserve_number = %s
    """, (reserve_num, reserve_num, reserve_num))
    
    # Show updated values
    pg_cur.execute("""
        SELECT total_amount_due, paid_amount, balance
        FROM charters
        WHERE reserve_number = %s
    """, (reserve_num,))
    updated = pg_cur.fetchone()
    
    print(f"\n  UPDATED:    Total=${float(updated[0]):.2f}  Paid=${float(updated[1]):.2f}  Balance=${float(updated[2]):.2f}")
    
    # Check if fixed
    if abs(float(updated[1]) - lms_paid) < 0.02:
        print(f"  ✓ FIXED")
        total_fixed += 1
    else:
        print(f"  ⚠ STILL MISMATCH")

pg_conn.commit()

print(f"\n{'='*100}")
print(f"SUMMARY")
print(f"{'='*100}")
print(f"Charters processed: {len(problem_charters)}")
print(f"Payments imported: {total_imported}")
print(f"Charters fixed: {total_fixed}")

pg_cur.close()
pg_conn.close()
lms_cur.close()
lms_conn.close()

print("\n")
