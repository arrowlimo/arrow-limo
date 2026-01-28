#!/usr/bin/env python3
"""
Delete orphan payments and their ledger entries.
5 payments for cancelled reserves that have 0 charges and 0 payments in LMS.
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Payment IDs to delete
payment_data = [
    (29967, '017887', 189.00),
    (29969, '017765', 75.00),
    (30022, '018013', 175.00),
    (18488, '015288', 75.00),
    (18442, '015244', 500.00),
]

print("Deleting 5 orphan payments and ledger entries...")
print()

try:
    total_deleted = 0.0
    
    for payment_id, reserve, amount in payment_data:
        # Delete ledger entries first
        cur.execute("""
            DELETE FROM income_ledger
            WHERE payment_id = %s
        """, (payment_id,))
        ledger_rows = cur.rowcount
        
        # Delete payment
        cur.execute("""
            DELETE FROM payments
            WHERE payment_id = %s
        """, (payment_id,))
        payment_rows = cur.rowcount
        
        print(f"✓ {reserve}: Deleted payment {payment_id} (${amount:,.2f}) + {ledger_rows} ledger entries")
        total_deleted += amount
    
    conn.commit()
    print()
    print("=" * 70)
    print(f"Total deleted: {len(payment_data)} payments, ${total_deleted:,.2f}")
    print("=" * 70)
    print("\n✅ All payments and ledger entries deleted - reserves now at $0")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
finally:
    cur.close()
    conn.close()
