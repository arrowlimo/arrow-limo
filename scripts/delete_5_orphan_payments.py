#!/usr/bin/env python3
"""
Delete the 5 payments that shouldn't exist (cancelled reserves with 0 payments in LMS).
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

# Payment IDs to delete
PAYMENT_IDS = [
    29967,  # 017887: $189.00 refund
    # Will get other 4 IDs
]

# Get all 5 first
conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

reserves = ['017887', '017765', '018013', '015288', '015244']

print("Getting payment IDs for 5 reserves to delete...")
print()

all_payments = []
for reserve in reserves:
    cur.execute("""
        SELECT payment_id, amount, payment_date, payment_method
        FROM payments
        WHERE reserve_number = %s
    """, (reserve,))
    
    payments = cur.fetchall()
    for payment_id, amount, payment_date, method in payments:
        all_payments.append((payment_id, reserve, amount, payment_date, method))
        print(f"{reserve}: Payment ID {payment_id}, ${float(amount):,.2f} ({payment_date})")

print()

if all_payments:
    print(f"Deleting {len(all_payments)} payments...")
    print()
    
    try:
        total_deleted = 0.0
        for payment_id, reserve, amount, payment_date, method in all_payments:
            cur.execute("DELETE FROM payments WHERE payment_id = %s", (payment_id,))
            total_deleted += float(amount)
            print(f"✓ Deleted payment ID {payment_id} ({reserve}): ${float(amount):,.2f}")
        
        conn.commit()
        print()
        print("=" * 70)
        print(f"Total deleted: {len(all_payments)} payments, ${total_deleted:,.2f}")
        print("=" * 70)
        print("\n✅ Payments deleted - reserves now show $0 balance")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
else:
    print("No payments found")

cur.close()
conn.close()
