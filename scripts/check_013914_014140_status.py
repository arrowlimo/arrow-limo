"""Check 013914 and 014140 payment status"""
import psycopg2, os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REMOVED***')
)
cur = conn.cursor()

print("Charter 013914 Payments:")
cur.execute("""
    SELECT payment_id, amount, payment_date, payment_key, charter_id, reserve_number
    FROM payments 
    WHERE reserve_number = '013914'
    ORDER BY payment_date
""")
for row in cur.fetchall():
    pid, amt, pdate, key, cid, res = row
    amt_str = f"${amt:.2f}" if amt else "$0.00"
    print(f"  ID {pid}: {amt_str} on {pdate}, key={key}, charter_id={cid}")

cur.execute("SELECT COUNT(*), SUM(amount) FROM payments WHERE reserve_number = '013914'")
count, total = cur.fetchone()
total_str = f"${total:.2f}" if total else "$0.00"
print(f"  Total: {count} payments = {total_str}\n")

print("Charter 014140 Payments:")
cur.execute("""
    SELECT payment_id, amount, payment_date, payment_key, charter_id, reserve_number
    FROM payments 
    WHERE reserve_number = '014140'
    ORDER BY payment_date
""")
for row in cur.fetchall():
    pid, amt, pdate, key, cid, res = row
    amt_str = f"${amt:.2f}" if amt else "$0.00"
    print(f"  ID {pid}: {amt_str} on {pdate}, key={key}, charter_id={cid}")

cur.execute("SELECT COUNT(*), SUM(amount) FROM payments WHERE reserve_number = '014140'")
count, total = cur.fetchone()
total_str = f"${total:.2f}" if total else "$0.00"
print(f"  Total: {count} payments = {total_str}\n")

# Check charter records
cur.execute("""
    SELECT reserve_number, total_amount_due, paid_amount, balance
    FROM charters
    WHERE reserve_number IN ('013914', '014140')
    ORDER BY reserve_number
""")
print("Charter Records:")
for row in cur.fetchall():
    res, due, paid, bal = row
    print(f"  {res}: Due ${due:.2f}, Paid ${paid:.2f}, Balance ${bal:.2f}")

cur.close()
conn.close()
