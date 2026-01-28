import psycopg2
import pyodbc

# LMS
lms_conn = pyodbc.connect(r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\\limo\\backups\\lms.mdb;')
lms_cur = lms_conn.cursor()

print("=== LMS Reserve 014140 ===")
lms_cur.execute("SELECT Reserve_No, Est_Charge, Balance, Status, Closed FROM Reserve WHERE Reserve_No = ?", ('014140',))
lms_reserve = lms_cur.fetchone()
if lms_reserve:
    print(f"Reserve: {lms_reserve[0]} | Est_Charge: ${lms_reserve[1]} | Balance: ${lms_reserve[2]} | Status: {lms_reserve[3]} | Closed: {lms_reserve[4]}")
else:
    print("NOT FOUND in LMS Reserve")

print("\nLMS Payments for 014140:")
lms_cur.execute("SELECT PaymentID, Reserve_No, Amount, LastUpdated, Key FROM Payment WHERE Reserve_No = ?", ('014140',))
lms_payments = lms_cur.fetchall()
if lms_payments:
    for p in lms_payments:
        print(f"  PaymentID={p[0]} | Amount=${p[2]} | Date={p[3]} | Key={p[4]}")
else:
    print("  No payments in LMS")

lms_cur.close()
lms_conn.close()

# ALMS
alms_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
alms_cur = alms_conn.cursor()

print("\n=== ALMS Charter 014140 ===")
alms_cur.execute("""
    SELECT charter_id, reserve_number, total_amount_due, paid_amount, balance, status
    FROM charters
    WHERE reserve_number = '014140'
""")
alms_charter = alms_cur.fetchone()
if alms_charter:
    print(f"CharterID: {alms_charter[0]} | Reserve: {alms_charter[1]} | Total: ${alms_charter[2]} | Paid: ${alms_charter[3]} | Balance: ${alms_charter[4]} | Status: {alms_charter[5]}")
else:
    print("NOT FOUND in ALMS charters")

print("\nALMS Payments for 014140:")
alms_cur.execute("""
    SELECT payment_id, reserve_number, amount, payment_date, payment_key, reference_number
    FROM payments
    WHERE reserve_number = '014140'
    ORDER BY payment_id
""")
alms_payments = alms_cur.fetchall()
if alms_payments:
    total = 0
    for p in alms_payments:
        total += float(p[2] or 0)
        print(f"  PaymentID={p[0]} | Amount=${p[2]} | Date={p[3]} | Key={p[4]} | Ref={p[5]}")
    print(f"  Total ALMS payments: ${total}")
else:
    print("  No payments in ALMS")

alms_cur.close()
alms_conn.close()
