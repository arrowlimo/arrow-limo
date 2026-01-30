"""
Investigate the remaining 19 overpaid reserves
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")

print("=" * 100)
print("INVESTIGATING REMAINING 19 OVERPAID RESERVES")
print("=" * 100)

try:
    alms_conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    alms_cursor = alms_conn.cursor()
    
    # Get all remaining overpaid reserves
    alms_cursor.execute("""
        SELECT c.charter_id, c.reserve_number, c.total_amount_due, c.balance, cl.name
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.balance < 0
        ORDER BY c.reserve_number
    """)
    
    remaining = alms_cursor.fetchall()
    
    print(f"\nFound {len(remaining)} remaining overpaid reserves:")
    print("-" * 100)
    
    for charter_id, reserve_num, total_due, balance, client_name in remaining:
        # Get all payments for this charter
        alms_cursor.execute("""
            SELECT p.payment_id, p.amount, p.payment_date, p.payment_method, p.created_at
            FROM payments p
            WHERE p.reserve_number = %s
            ORDER BY p.payment_date
        """, (reserve_num,))
        
        payments = alms_cursor.fetchall()
        total_paid = sum([p[1] for p in payments if p[1]])
        
        print(f"\nReserve {reserve_num} ({client_name}):")
        print(f"  Charter ID:      {charter_id}")
        print(f"  Total Due:       ${total_due:.2f}")
        print(f"  Total Paid:      ${total_paid:.2f}")
        print(f"  Balance:         ${balance:.2f} (OVERPAID)")
        print(f"  Overpay Amount:  ${abs(balance):.2f}")
        print(f"  Payments ({len(payments)} records):")
        
        for p_id, amount, p_date, method, created in payments:
            print(f"    {p_date} | ${amount:8.2f} | {method:15}")
    
    alms_conn.close()
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
