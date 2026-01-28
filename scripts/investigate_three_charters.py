"""
Investigate why 016086, 013690, and 017720 show mismatches after fix attempt.
"""

import pyodbc
import psycopg2

# LMS Access database
LMS_PATH = r'L:\limo\backups\lms.mdb'
lms_conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')

# PostgreSQL database
pg_conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

CHARTERS = ['016086', '013690', '017720']

for reserve_no in CHARTERS:
    print(f"\n{'='*80}")
    print(f"CHARTER {reserve_no}")
    print(f"{'='*80}")
    
    # LMS data
    cur = lms_conn.cursor()
    cur.execute("""
        SELECT PaymentID, [Key], LastUpdated, Amount
        FROM Payment
        WHERE Reserve_No = ?
        ORDER BY LastUpdated
    """, (reserve_no,))
    lms_payments = cur.fetchall()
    
    print(f"\nLMS PAYMENTS ({len(lms_payments)} total):")
    lms_total = 0
    for p in lms_payments:
        payment_id, key, date, amount = p
        lms_total += float(amount)
        print(f"  PaymentID {payment_id}: ${amount:>10.2f} on {date} [Key: {key}]")
    print(f"  LMS TOTAL: ${lms_total:.2f}")
    
    # PostgreSQL data
    cur = pg_conn.cursor()
    cur.execute("""
        SELECT payment_id, payment_key, payment_date, amount
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date
    """, (reserve_no,))
    pg_payments = cur.fetchall()
    
    print(f"\nPOSTGRESQL PAYMENTS ({len(pg_payments)} total):")
    pg_total = 0
    for p in pg_payments:
        payment_id, key, date, amount = p
        pg_total += float(amount)
        print(f"  ID {payment_id}: ${amount:>10.2f} on {date} [Key: {key}]")
    print(f"  POSTGRESQL TOTAL: ${pg_total:.2f}")
    
    # Comparison
    print(f"\nCOMPARISON:")
    print(f"  LMS Total:        ${lms_total:.2f}")
    print(f"  PostgreSQL Total: ${pg_total:.2f}")
    print(f"  Difference:       ${pg_total - lms_total:.2f}")
    
    if abs(pg_total - lms_total) > 0.02:
        print(f"  STATUS: MISMATCH - need to investigate")
    else:
        print(f"  STATUS: OK")

lms_conn.close()
pg_conn.close()
