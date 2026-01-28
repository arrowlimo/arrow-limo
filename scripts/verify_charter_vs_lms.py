"""
Match payments from LMS using proper table relationships.
LMS is the source of truth - use Reserve_No to link Payment table to Reserve table.
"""

import psycopg2
import pyodbc
import os

# PostgreSQL connection
def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

# LMS Access connection
LMS_PATH = r'L:\limo\backups\lms.mdb'
conn_str = (
    r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
    r'DBQ=L:\limo\backups\lms.mdb;'
)
lms_conn = pyodbc.connect(conn_str)
lms_cur = lms_conn.cursor()

# Get top overpaid charter from PostgreSQL
pg_conn = get_pg_connection()
pg_cur = pg_conn.cursor()

pg_cur.execute("""
    SELECT reserve_number, total_amount_due, paid_amount, balance
    FROM charters
    WHERE balance < 0
    ORDER BY balance
    LIMIT 1
""")

reserve, pg_total, pg_paid, pg_balance = pg_cur.fetchone()

print("=" * 80)
print(f"VERIFY CHARTER {reserve} AGAINST LMS")
print("=" * 80)

print(f"\n📊 POSTGRESQL DATA:")
print(f"   Total Due: ${pg_total:,.2f}")
print(f"   Paid Amount: ${pg_paid:,.2f}")
print(f"   Balance: ${pg_balance:,.2f}")

# Get LMS Reserve data
lms_cur.execute("""
    SELECT Reserve_No, Est_Charge, Deposit, Balance, Pymt_Type
    FROM Reserve
    WHERE Reserve_No = ?
""", (reserve,))

lms_reserve = lms_cur.fetchone()

if lms_reserve:
    lms_reserve_no, lms_est_charge, lms_deposit, lms_balance, lms_pymt_type = lms_reserve
    print(f"\n📊 LMS RESERVE DATA:")
    print(f"   Est_Charge (Total): ${lms_est_charge or 0:,.2f}")
    print(f"   Deposit (Paid): ${lms_deposit or 0:,.2f}")
    print(f"   Balance: ${lms_balance or 0:,.2f}")
    print(f"   Pymt_Type: {lms_pymt_type or 'N/A'}")
else:
    print(f"\n[WARN]  Reserve {reserve} NOT FOUND in LMS")

# Get LMS Payment table data
lms_cur.execute("""
    SELECT PaymentID, Reserve_No, Amount, LastUpdated, LastUpdatedBy, [Key]
    FROM Payment
    WHERE Reserve_No = ?
    ORDER BY LastUpdated
""", (reserve,))

lms_payments = lms_cur.fetchall()

print(f"\n📊 LMS PAYMENT TABLE ({len(lms_payments)} payments):")
if lms_payments:
    lms_total = sum(p[2] or 0 for p in lms_payments)
    print(f"   Total from Payment table: ${lms_total:,.2f}")
    print(f"\n   Details:")
    for p in lms_payments:
        print(f"      PaymentID {p[0]}: ${p[2] or 0:,.2f} on {p[3]} by {p[4] or 'unknown'} (Key: {p[5] or 'N/A'})")
else:
    print("   No payments in LMS Payment table")

# Get PostgreSQL payments
pg_cur.execute("""
    SELECT payment_id, payment_date, amount, payment_method, 
           LEFT(notes, 60) as notes_short
    FROM payments
    WHERE reserve_number = %s
    ORDER BY payment_date
""", (reserve,))

pg_payments = pg_cur.fetchall()

print(f"\n📊 POSTGRESQL PAYMENTS ({len(pg_payments)} payments):")
if pg_payments:
    pg_total = sum(p[2] for p in pg_payments)
    print(f"   Total: ${pg_total:,.2f}")
    print(f"\n   Details:")
    for p in pg_payments:
        print(f"      ID {p[0]}: {p[1]} ${p[2]:,.2f} ({p[3] or 'unknown'}) - {p[4] or ''}")

# Compare
print(f"\n{'='*80}")
print("COMPARISON")
print("=" * 80)

if lms_reserve:
    print(f"\n✓ LMS Est_Charge: ${lms_est_charge or 0:,.2f}")
    print(f"  PG Total Due:   ${pg_total:,.2f}")
    print(f"  Match: {'✓' if abs((lms_est_charge or 0) - pg_total) < 0.01 else '✗ MISMATCH'}")
    
    print(f"\n✓ LMS Deposit: ${lms_deposit or 0:,.2f}")
    print(f"  LMS Payments: ${sum(p[2] or 0 for p in lms_payments):,.2f}")
    print(f"  PG Paid:      ${pg_paid:,.2f}")
    
    lms_actual_paid = lms_deposit or sum(p[2] or 0 for p in lms_payments)
    print(f"\n  LMS Actual Paid (Deposit or Payment sum): ${lms_actual_paid:,.2f}")
    print(f"  Match: {'✓' if abs(lms_actual_paid - pg_paid) < 0.01 else '✗ MISMATCH'}")

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
