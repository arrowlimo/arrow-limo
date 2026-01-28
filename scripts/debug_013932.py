import psycopg2

c = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = c.cursor()

# Get reserve 013932 details
cur.execute("""
    SELECT c.charter_id, c.reserve_number, c.client_id, cl.client_name, 
           c.total_amount_due, c.paid_amount, c.balance
    FROM charters c
    LEFT JOIN clients cl ON cl.client_id = c.client_id
    WHERE c.reserve_number = '013932'
""")
charter = cur.fetchone()
print(f"Charter 013932:")
print(f"  Charter ID: {charter[0]}")
print(f"  Client: {charter[3]} (ID: {charter[2]})")
print(f"  Due: ${charter[4]:.2f}, Paid: ${charter[5]:.2f}, Balance: ${charter[6]:.2f}")
print()

# Get all payments for this reserve
cur.execute("""
    SELECT payment_id, payment_date, amount, payment_key, created_at
    FROM payments
    WHERE reserve_number = '013932'
    ORDER BY payment_date
""")
payments = cur.fetchall()
print(f"Payments attached to 013932: {len(payments)}")
for p in payments:
    print(f"  ID={p[0]:5d} date={p[1]} amt=${p[2]:6.2f} key={p[3] or 'NULL':20s} created={p[4]}")
print()

# Check LMS
import pyodbc
lms_conn = pyodbc.connect(r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;')
lms_cur = lms_conn.cursor()
lms_cur.execute("SELECT Deposit FROM Reserve WHERE Reserve_No = ?", ('013932',))
lms_deposit = lms_cur.fetchone()
print(f"LMS shows Deposit: ${lms_deposit[0] if lms_deposit else 0:.2f}")
print()

# Check credit ledger
cur.execute("""
    SELECT credit_id, credit_amount, remaining_balance
    FROM charter_credit_ledger
    WHERE source_reserve_number = '013932'
""")
credit = cur.fetchone()
if credit:
    print(f"Credit created: ID={credit[0]}, amount=${credit[1]:.2f}, remaining=${credit[2]:.2f}")
else:
    print("No credit found")
