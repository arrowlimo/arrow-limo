#!/usr/bin/env python3
"""
Roll back duplicate payments and recalculate charter balances.
"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Charters that got duplicate payments
problem_charters = ['016086', '013690', '017720', '018199']

print("\n" + "="*80)
print("ROLLING BACK DUPLICATE PAYMENTS")
print("="*80)

for reserve_num in problem_charters:
    print(f"\nCharter {reserve_num}:")
    
    # Show current payments
    cur.execute("""
        SELECT payment_id, payment_date, amount, payment_key, created_at
        FROM payments
        WHERE reserve_number = %s
        ORDER BY created_at DESC
    """, (reserve_num,))
    
    payments = cur.fetchall()
    print(f"  Total payments: {len(payments)}")
    
    # Identify today's imports (most recent created_at)
    if payments:
        latest_created = payments[0][4]
        today_imports = [p for p in payments if p[4] == latest_created]
        
        if today_imports:
            print(f"  Today's imports: {len(today_imports)} payments")
            for p_id, p_date, amt, key, created in today_imports:
                print(f"    ID {p_id}: ${amt:.2f} on {p_date} - {key}")
            
            response = input(f"  Delete these {len(today_imports)} payments? (yes/no): ")
            if response.lower() == 'yes':
                for p_id, _, _, _, _ in today_imports:
                    cur.execute("DELETE FROM payments WHERE payment_id = %s", (p_id,))
                print(f"  ✓ Deleted {len(today_imports)} payments")

# Recalculate all affected charters
print("\n" + "="*80)
print("RECALCULATING CHARTER BALANCES")
print("="*80)

for reserve_num in problem_charters + ['019727']:
    cur.execute("""
        UPDATE charters
        SET paid_amount = (
            SELECT COALESCE(SUM(amount), 0)
            FROM payments
            WHERE reserve_number = %s
        ),
        balance = total_amount_due - (
            SELECT COALESCE(SUM(amount), 0)
            FROM payments
            WHERE reserve_number = %s
        )
        WHERE reserve_number = %s
        RETURNING total_amount_due, paid_amount, balance
    """, (reserve_num, reserve_num, reserve_num))
    
    result = cur.fetchone()
    if result:
        print(f"{reserve_num}: Total=${result[0]:.2f} Paid=${result[1]:.2f} Balance=${result[2]:.2f}")

conn.commit()
cur.close()
conn.close()

print("\n✓ Done\n")
