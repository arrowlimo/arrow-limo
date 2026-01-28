import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("=" * 80)
print("CHARTER 016461 ANALYSIS")
print("=" * 80)

# Get charter details
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, client_id, 
           total_amount_due, paid_amount, balance, cancelled
    FROM charters 
    WHERE reserve_number = '016461'
""")
charter = cur.fetchone()
if charter:
    print(f"\nCharter ID: {charter[0]}")
    print(f"Reserve Number: {charter[1]}")
    print(f"Charter Date: {charter[2]}")
    print(f"Client ID: {charter[3]}")
    print(f"Total Due: ${charter[4]}")
    print(f"Paid Amount: ${charter[5]}")
    print(f"Balance: ${charter[6]}")
    print(f"Cancelled: {charter[7]}")
else:
    print("Charter not found!")

# Get payments
print("\n" + "=" * 80)
print("PAYMENTS:")
print("=" * 80)
cur.execute("""
    SELECT payment_id, amount, payment_date, payment_method, payment_key, notes
    FROM payments 
    WHERE reserve_number = '016461'
    ORDER BY payment_date
""")
payments = cur.fetchall()
if payments:
    for p in payments:
        print(f"\nPayment ID: {p[0]}")
        print(f"Amount: ${p[1]}")
        print(f"Date: {p[2]}")
        print(f"Method: {p[3]}")
        print(f"Key: {p[4]}")
        if p[5]:
            print(f"Notes: {p[5]}")
    print(f"\nTotal Payments: ${sum(p[1] for p in payments)}")
else:
    print("No payments found")

# Get credits
print("\n" + "=" * 80)
print("CREDITS:")
print("=" * 80)
cur.execute("""
    SELECT id, source_reserve_number, target_reserve_number, credit_amount, 
           remaining_balance, credit_reason, notes, created_at
    FROM charter_credit_ledger 
    WHERE source_reserve_number = '016461' OR target_reserve_number = '016461'
""")
credits = cur.fetchall()
if credits:
    for c in credits:
        print(f"\nCredit ID: {c[0]}")
        print(f"Source Charter: {c[1]}")
        print(f"Target Charter: {c[2]}")
        print(f"Credit Amount: ${c[3]}")
        print(f"Remaining Balance: ${c[4]}")
        print(f"Reason: {c[5]}")
        if c[6]:
            print(f"Notes: {c[6]}")
        print(f"Created: {c[7]}")
else:
    print("No credits found")

cur.close()
conn.close()
