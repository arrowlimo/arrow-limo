"""
Deep dive analysis of the two charters with balance errors
"""
import psycopg2
import os

pg_conn = psycopg2.connect(
    host='localhost', database='almsdata',
    user='postgres', password='***REDACTED***'
)
pg_cur = pg_conn.cursor()

reserves = ['016312', '016530']

for reserve in reserves:
    print(f"\n{'='*100}")
    print(f"CHARTER {reserve} - DETAILED ANALYSIS")
    print(f"{'='*100}")
    
    # Charter data
    pg_cur.execute("""
        SELECT charter_id, reserve_number, total_amount_due, paid_amount, balance, cancelled
        FROM charters WHERE reserve_number = %s
    """, (reserve,))
    charter = pg_cur.fetchone()
    
    print(f"\nCharter Record:")
    print(f"  Charter ID: {charter[0]}")
    print(f"  Total Due: ${charter[2]:,.2f}")
    print(f"  Stored Paid: ${charter[3]:,.2f}")
    print(f"  Stored Balance: ${charter[4]:,.2f}")
    print(f"  Cancelled: {charter[5]}")
    
    # All payments
    print(f"\nAll Payments for this reserve:")
    pg_cur.execute("""
        SELECT payment_id, amount, payment_date, payment_method, payment_key, created_at
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date, payment_id
    """, (reserve,))
    payments = pg_cur.fetchall()
    
    total_paid = 0
    for pmt in payments:
        print(f"  Payment {pmt[0]}: ${pmt[1]:,.2f} on {pmt[2]} via {pmt[3]} (key:{pmt[4]}, created:{pmt[5]})")
        total_paid += pmt[1]
    
    print(f"\n  ACTUAL TOTAL PAID: ${total_paid:,.2f}")
    print(f"  STORED paid_amount: ${charter[3]:,.2f}")
    print(f"  DIFFERENCE: ${total_paid - charter[3]:,.2f}")
    
    calculated_balance = charter[2] - total_paid
    print(f"\n  CALCULATED balance: ${calculated_balance:,.2f}")
    print(f"  STORED balance: ${charter[4]:,.2f}")
    print(f"  DIFFERENCE: ${calculated_balance - charter[4]:,.2f}")
    
    # Check for duplicate payments
    pg_cur.execute("""
        SELECT amount, payment_date, COUNT(*) as count,
               STRING_AGG(payment_id::text, ', ') as ids
        FROM payments
        WHERE reserve_number = %s
        GROUP BY amount, payment_date
        HAVING COUNT(*) > 1
    """, (reserve,))
    dups = pg_cur.fetchall()
    
    if dups:
        print(f"\n⚠️  DUPLICATE PAYMENTS DETECTED:")
        for dup in dups:
            print(f"  Amount ${dup[0]:,.2f} on {dup[1]}: {dup[2]} copies (IDs: {dup[3]})")

pg_cur.close()
pg_conn.close()
