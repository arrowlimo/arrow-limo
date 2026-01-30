#!/usr/bin/env python3
"""
Import missing payments for charter 019209 from LMS.
Missing: 3 x $500 payments from June 30, 2025
"""

import psycopg2
import pyodbc
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def get_lms_connection():
    LMS_PATH = r'L:\limo\backups\lms.mdb'
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

# Get LMS payments
lms_conn = get_lms_connection()
lms_cur = lms_conn.cursor()

lms_cur.execute("""
    SELECT PaymentID, [Key], LastUpdated, Amount, LastUpdatedBy
    FROM Payment
    WHERE Reserve_No = '019209'
    ORDER BY LastUpdated
""")

lms_payments = lms_cur.fetchall()

print("\n" + "="*80)
print("LMS PAYMENTS FOR 019209")
print("="*80)
for payment_id, key, date, amt, by_who in lms_payments:
    print(f"PaymentID:{payment_id:<8} Key:{key:<15} {date} ${amt:>10.2f} by {by_who}")

# Get PostgreSQL payments
pg_conn = get_db_connection()
pg_cur = pg_conn.cursor()

pg_cur.execute("""
    SELECT payment_id, payment_key, payment_date, amount
    FROM payments
    WHERE reserve_number = '019209'
    ORDER BY payment_date
""")

pg_payments = pg_cur.fetchall()

print("\n" + "="*80)
print("POSTGRESQL PAYMENTS FOR 019209")
print("="*80)
for payment_id, key, date, amt in pg_payments:
    print(f"PaymentID:{payment_id:<8} Key:{key:<25} {date} ${float(amt):>10.2f}")

# Find missing payments
print("\n" + "="*80)
print("IDENTIFYING MISSING PAYMENTS")
print("="*80)

pg_keys = {p[1] for p in pg_payments}
missing_payments = []

for payment_id, key, date, amt, by_who in lms_payments:
    lms_key = f"LMS:{payment_id}"
    if lms_key not in pg_keys:
        missing_payments.append({
            'payment_id': payment_id,
            'key': key,
            'date': date,
            'amount': float(amt),
            'by': by_who
        })
        print(f"MISSING: PaymentID {payment_id} Key:{key} ${amt:.2f} on {date}")

if missing_payments:
    print(f"\n{len(missing_payments)} missing payments totaling ${sum([p['amount'] for p in missing_payments]):.2f}")
    
    response = input("\nImport these missing payments? (yes/no): ")
    
    if response.lower() == 'yes':
        for mp in missing_payments:
            pg_cur.execute("""
                INSERT INTO payments (
                    reserve_number, amount, payment_date, payment_method,
                    payment_key, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                '019209',
                mp['amount'],
                mp['date'].date(),
                'unknown',
                f"LMS:{mp['payment_id']}",
                f"Imported from LMS Payment ID {mp['payment_id']}"
            ))
            print(f"  Imported: ${mp['amount']:.2f} on {mp['date'].date()}")
        
        # Recalculate charter paid_amount and balance
        pg_cur.execute("""
            UPDATE charters
            SET paid_amount = (
                SELECT COALESCE(SUM(amount), 0)
                FROM payments
                WHERE reserve_number = '019209'
            ),
            balance = total_amount_due - (
                SELECT COALESCE(SUM(amount), 0)
                FROM payments
                WHERE reserve_number = '019209'
            )
            WHERE reserve_number = '019209'
        """)
        
        pg_conn.commit()
        
        print(f"\n✓ Imported {len(missing_payments)} payments")
        print("✓ Recalculated charter 019209 balance")
        
        # Show updated charter
        pg_cur.execute("""
            SELECT total_amount_due, paid_amount, balance
            FROM charters
            WHERE reserve_number = '019209'
        """)
        charter = pg_cur.fetchone()
        print(f"\nUpdated Charter 019209:")
        print(f"  Total Due: ${float(charter[0]):.2f}")
        print(f"  Paid: ${float(charter[1]):.2f}")
        print(f"  Balance: ${float(charter[2]):.2f}")
    else:
        print("\nImport cancelled")
else:
    print("\nNo missing payments found")

pg_cur.close()
pg_conn.close()
lms_cur.close()
lms_conn.close()

print("\n")
