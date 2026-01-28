#!/usr/bin/env python3
"""Check if the 14 cancelled charters with drivers have payments"""
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=" * 70)
print("CANCELLED CHARTERS WITH DRIVERS - PAYMENT CHECK")
print("=" * 70)

# Get the 14 cancelled charters with drivers
cur.execute("""
    SELECT c.charter_id, c.reserve_number, c.charter_date, 
           c.total_amount_due, c.paid_amount, c.balance,
           e.full_name as driver_name,
           (SELECT COUNT(*) FROM payments p WHERE p.charter_id = c.charter_id) as payment_count,
           (SELECT SUM(amount) FROM payments p WHERE p.charter_id = c.charter_id) as payment_total,
           (SELECT SUM(gross_pay) FROM driver_payroll dp 
            WHERE dp.charter_id::integer = c.charter_id 
            AND (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)) as driver_pay
    FROM charters c
    LEFT JOIN employees e ON e.employee_id = c.assigned_driver_id
    WHERE c.cancelled = true
    AND c.assigned_driver_id IS NOT NULL
    ORDER BY c.charter_date DESC
""")

cancelled = cur.fetchall()

print(f"\n📊 FOUND {len(cancelled)} CANCELLED CHARTERS WITH DRIVERS:\n")

total_payments = 0
total_driver_pay = 0
charters_with_payments = 0

for row in cancelled:
    has_payment = row['payment_count'] > 0
    if has_payment:
        charters_with_payments += 1
        total_payments += row['payment_total'] or 0
    
    total_driver_pay += row['driver_pay'] or 0
    
    print(f"Charter {row['reserve_number']} ({row['charter_date']}):")
    print(f"   Driver: {row['driver_name']}")
    print(f"   Total due: ${row['total_amount_due'] or 0:.2f}")
    print(f"   Paid: ${row['paid_amount'] or 0:.2f}")
    print(f"   Balance: ${row['balance'] or 0:.2f}")
    print(f"   Payments: {row['payment_count']} (${row['payment_total'] or 0:.2f})")
    print(f"   Driver pay: ${row['driver_pay'] or 0:.2f}")
    
    if has_payment:
        # Show payment details
        cur.execute("""
            SELECT payment_id, amount, payment_date, payment_method
            FROM payments
            WHERE charter_id = %s
            ORDER BY payment_date
        """, (row['charter_id'],))
        
        payments = cur.fetchall()
        for p in payments:
            print(f"      → Payment: ${p['amount']:.2f} on {p['payment_date']} via {p['payment_method']}")
    
    print()

print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"\nCancelled charters with drivers: {len(cancelled)}")
print(f"Charters with payments: {charters_with_payments} ({charters_with_payments/len(cancelled)*100:.1f}%)")
print(f"Charters without payments: {len(cancelled) - charters_with_payments}")
print(f"\nTotal payments received: ${total_payments:.2f}")
print(f"Total driver pay: ${total_driver_pay:.2f}")
print(f"Net cost of cancellations: ${total_driver_pay - total_payments:.2f}")

conn.close()
