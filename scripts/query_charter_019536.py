import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute("""
    SELECT charter_id, reserve_number, charter_date, pickup_time, pickup_address, 
           dropoff_address, client_id, vehicle, vehicle_id, driver, assigned_driver_id, 
           employee_id, rate, total_amount_due, paid_amount, balance, status, 
           booking_notes, driver_notes, vehicle_notes, notes
    FROM charters 
    WHERE reserve_number = '019536'
""")
r = cur.fetchone()

if r:
    print("\nCharter 019536 Details:")
    print("=" * 80)
    for k, v in r.items():
        print(f"{k:<25} {v}")
    
    # Check for charter_charges
    cur.execute("SELECT * FROM charter_charges WHERE charter_id = %s", (r['charter_id'],))
    charges = cur.fetchall()
    print(f"\nCharter Charges: {len(charges)} rows")
    for c in charges:
        print(f"  {c}")
    
    # Check for payments
    cur.execute("SELECT * FROM payments WHERE reserve_number = '019536'")
    payments = cur.fetchall()
    print(f"\nPayments: {len(payments)} rows")
    for p in payments:
        print(f"  payment_id={p['payment_id']} amount={p['amount']} date={p.get('payment_date')} method={p.get('payment_method')}")
else:
    print("Charter 019536 not found")

cur.close()
conn.close()
