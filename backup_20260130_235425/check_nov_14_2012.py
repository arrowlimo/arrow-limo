"""Check charters on November 14, 2012"""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

# Count charters on Nov 14, 2012
cur.execute("""
    SELECT COUNT(*)
    FROM charters 
    WHERE charter_date = '2012-11-14'
""")

count = cur.fetchone()[0]
print(f"\n{'='*60}")
print(f"Charters on November 14, 2012: {count}")
print(f"{'='*60}")

if count > 0:
    cur.execute("""
        SELECT 
            c.reserve_number,
            COALESCE(cl.company_name, cl.client_name) as client,
            c.booking_status,
            c.total_amount_due,
            e.full_name as driver,
            v.vehicle_number
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        LEFT JOIN employees e ON c.employee_id = e.employee_id
        LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
        WHERE charter_date = '2012-11-14'
        ORDER BY c.reserve_number
    """)
    
    print("\nDetails:")
    for row in cur.fetchall():
        res, client, status, total, driver, vehicle = row
        print(f"\n  Reserve: {res}")
        print(f"    Client: {client}")
        print(f"    Status: {status}")
        print(f"    Total: ${total:.2f}")
        print(f"    Driver: {driver or 'Not assigned'}")
        print(f"    Vehicle: {vehicle or 'Not assigned'}")

cur.close()
conn.close()
