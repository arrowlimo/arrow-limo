import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("Searching May 2012 with ANY Calgary reference and ~$600:\n")

# Broader search: May 2012, any charter with Calgary + ~$600
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due, paid_amount,
           client_id, pickup_address, dropoff_address, booking_notes, notes
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
    AND EXTRACT(MONTH FROM charter_date) = 5
    AND total_amount_due BETWEEN 550 AND 650
    ORDER BY charter_date DESC
    LIMIT 30
""")

may_2012 = cur.fetchall()
print(f"Found {len(may_2012)} charters in May 2012 around $600\n")
for c in may_2012:
    cid, reserve, date, total, paid, cid_val, pickup, dropoff, booking, notes = c
    paid_amt = paid if paid else 0
    print(f"Charter {cid:6d} | {reserve:8s} | {date} | ${total:10.2f} | Paid: ${paid_amt:10.2f}")
    if pickup:
        print(f"  Pickup: {pickup[:80]}")
    if dropoff:
        print(f"  Dropoff: {dropoff[:80]}")
    
    # Get client name
    cur.execute("SELECT client_name FROM clients WHERE client_id = %s", (cid_val,))
    client = cur.fetchone()
    if client:
        print(f"  Client: {client[0]}")
    
    if booking:
        print(f"  Booking: {booking[:120]}")
    if notes:
        print(f"  Notes: {notes[:120]}")
    print()

# Also search for any amount in May 2012 with David Richard reference
print("\n\nSearching entire May 2012 for any 'DAVID RICHARD' reference:")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due,
           booking_notes, notes
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
    AND EXTRACT(MONTH FROM charter_date) = 5
    AND (
        booking_notes ILIKE '%david richard%'
        OR notes ILIKE '%david richard%'
        OR booking_notes ILIKE '%david%'
        OR notes ILIKE '%david%'
    )
    ORDER BY charter_date DESC
    LIMIT 30
""")

david_charters = cur.fetchall()
print(f"Found {len(david_charters)} charters mentioning David\n")
for c in david_charters:
    cid, reserve, date, total, booking, notes = c
    print(f"Charter {cid:6d} | {reserve:8s} | {date} | ${total:10.2f}")
    if booking:
        print(f"  Booking: {booking[:100]}")
    if notes:
        print(f"  Notes: {notes[:100]}")
    print()

cur.close()
conn.close()
