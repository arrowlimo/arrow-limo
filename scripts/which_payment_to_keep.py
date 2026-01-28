"""
Investigate which of the 2 remaining payments for 013914/014140 is correct.
User confirmed: "014140 paid in full 500 dollars 013914 paid in full one payment"
"""
import psycopg2, os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REMOVED***')
)
cur = conn.cursor()

print("="*80)
print("ANALYSIS: Which payment to keep?")
print("="*80)
print()

for reserve in ['013914', '014140']:
    print(f"\nCharter {reserve}:")
    
    # Get charter info
    cur.execute("""
        SELECT charter_date, client_name, total_amount_due, status, cancelled
        FROM charters
        WHERE reserve_number = %s
    """, (reserve,))
    charter_info = cur.fetchone()
    if charter_info:
        cdate, client, due, status, cancelled = charter_info
        print(f"  Charter Date: {cdate}")
        print(f"  Client: {client}")
        print(f"  Total Due: ${due:.2f}")
        print(f"  Status: {status}, Cancelled: {cancelled}")
    
    # Get payments
    cur.execute("""
        SELECT payment_id, amount, payment_date, payment_key, payment_method,
               ABS(EXTRACT(EPOCH FROM (payment_date - %s::date))/86400) as days_diff
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date
    """, (cdate, reserve))
    
    print(f"\n  Payments:")
    for row in cur.fetchall():
        pid, amt, pdate, key, method, diff = row
        key_info = f"LMS key: {key}" if key else "No key (manual entry?)"
        print(f"    ID {pid}: ${amt:.2f} on {pdate} ({int(diff)} days from charter)")
        print(f"      {key_info}, Method: {method}")
    
    print()

print("="*80)
print("RECOMMENDATION:")
print("="*80)
print()
print("Both charters have 2 x $500 payments:")
print("  - One with payment_key (LMS import)")
print("  - One without key (earliest)")
print()
print("User confirmed both should have ONLY ONE $500 payment.")
print()
print("Question: Which payment is the ACTUAL payment?")
print("  A) Keep the LMS-keyed payment (16378 for 013914, 16860 for 014140)")
print("  B) Keep the earliest payment (28070 for 013914, 27797 for 014140)")
print("  C) Keep whichever is closest to charter date")
print()

cur.close()
conn.close()
