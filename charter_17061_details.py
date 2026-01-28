import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("CHARTER 17061 - DAVID RICHARD - OCT 17, 2023 - FULL DETAILS:\n")
print("=" * 100)

# Get full charter details
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, pickup_time, pickup_address,
           dropoff_address, total_amount_due, paid_amount, status, payment_status,
           booking_notes, notes, client_id, driver_name, driver_id
    FROM charters
    WHERE charter_id = 17061
""")

charter = cur.fetchone()
if charter:
    cid, reserve, date, pickup_time, pickup, dropoff, total, paid, status, payment_status, booking, notes, client_id, driver, driver_id = charter
    
    print(f"Charter ID: {cid}")
    print(f"Reserve Number: {reserve}")
    print(f"Date: {date}")
    print(f"Pickup Time: {pickup_time}")
    print(f"Status: {status}")
    print(f"Payment Status: {payment_status}")
    print()
    
    print(f"Total Amount Due: ${total:.2f}")
    paid_amt = paid if paid else 0
    print(f"Paid Amount: ${paid_amt:.2f}")
    print()
    
    print(f"Pickup Address: {pickup}")
    print(f"Dropoff Address: {dropoff}")
    print()
    
    # Get client details
    cur.execute("""
        SELECT client_id, client_name, company_name, email, primary_phone
        FROM clients
        WHERE client_id = %s
    """, (client_id,))
    
    client = cur.fetchone()
    if client:
        cid_val, cname, cname, email, phone = client
        print(f"Client: {cname}")
        print(f"Company: {cname}")
        print(f"Email: {email}")
        print(f"Phone: {phone}")
        print()
    
    print(f"Driver: {driver} (ID: {driver_id})")
    print()
    
    print("BOOKING NOTES:")
    print("-" * 100)
    if booking:
        print(booking)
    else:
        print("(No booking notes)")
    
    print()
    print("NOTES:")
    print("-" * 100)
    if notes:
        print(notes)
    else:
        print("(No notes)")
    
    # Get payments for this charter
    print()
    print("PAYMENTS FOR THIS CHARTER:")
    print("-" * 100)
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date, payment_method,
               status, notes
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date DESC
    """, (reserve,))
    
    payments = cur.fetchall()
    print(f"Found {len(payments)} payments\n")
    for p in payments:
        p_id, p_reserve, p_amount, p_date, p_method, p_status, p_notes = p
        print(f"  Payment {p_id:6d} | {p_date} | ${p_amount:10.2f} | {p_method:15s} | {p_status}")
        if p_notes:
            print(f"    Notes: {p_notes}")

cur.close()
conn.close()
