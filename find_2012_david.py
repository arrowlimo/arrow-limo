import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("Searching 2012 for David Richard medical appointment $600 charter:\n")

# Search entire 2012 for David Richard with medical + Calgary + $600
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due,
           booking_notes, notes, client_id
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
    AND total_amount_due BETWEEN 550 AND 650
    AND (
        (booking_notes ILIKE '%david%' AND booking_notes ILIKE '%calgary%')
        OR (notes ILIKE '%david%' AND notes ILIKE '%calgary%')
        OR (booking_notes ILIKE '%medical%' AND booking_notes ILIKE '%calgary%')
        OR (notes ILIKE '%medical%' AND notes ILIKE '%calgary%')
    )
    ORDER BY charter_date DESC
    LIMIT 30
""")

results = cur.fetchall()
print(f"Found {len(results)} 2012 charters with David/Medical + Calgary combo\n")
for c in results:
    cid, reserve, date, total, booking, notes, client_id = c
    print(f"Charter {cid:6d} | {reserve:8s} | {date} | ${total:10.2f}")
    
    # Get client
    cur.execute("SELECT client_name FROM clients WHERE client_id = %s", (client_id,))
    client = cur.fetchone()
    if client:
        print(f"  Client: {client[0]}")
    
    if booking:
        print(f"  Booking: {booking[:110]}")
    if notes:
        print(f"  Notes: {notes[:110]}")
    print()

# Try: Search all 2012 charters with exactly $600
print("\n\n2012 CHARTERS WITH EXACTLY $600:")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due,
           client_id, booking_notes, notes
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
    AND total_amount_due = 600.00
    ORDER BY charter_date DESC
    LIMIT 20
""")

exact_600 = cur.fetchall()
print(f"Found {len(exact_600)} charters with exactly $600\n")
for c in exact_600:
    cid, reserve, date, total, client_id, booking, notes = c
    
    cur.execute("SELECT client_name FROM clients WHERE client_id = %s", (client_id,))
    client = cur.fetchone()
    client_name = client[0] if client else f"ID {client_id}"
    
    print(f"Charter {cid:6d} | {reserve:8s} | {date} | ${total:10.2f}")
    print(f"  Client: {client_name}")
    if booking:
        print(f"  Booking: {booking[:80]}")
    if notes:
        print(f"  Notes: {notes[:80]}")
    print()

# Try: ALL 2012 charters mentioning David (any amount)
print("\n\n2012 CHARTERS mentioning 'DAVID' (any amount):")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due,
           booking_notes, notes, client_id
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
    AND (
        booking_notes ILIKE '%david%'
        OR notes ILIKE '%david%'
    )
    ORDER BY total_amount_due DESC
    LIMIT 30
""")

david_2012 = cur.fetchall()
print(f"Found {len(david_2012)} charters mentioning David\n")
for c in david_2012[:20]:
    cid, reserve, date, total, booking, notes, client_id = c
    print(f"Charter {cid:6d} | {reserve:8s} | {date} | ${total:10.2f}")
    if booking and len(booking) < 200:
        print(f"  {booking[:100]}")
    if notes and len(notes) < 200:
        print(f"  {notes[:100]}")
    print()

cur.close()
conn.close()
