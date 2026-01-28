import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("Searching for: October 17, 2023 + BLUE CROSS + DAVID + REFUND\n")

# Search for Oct 17, 2023 charters
print("1️⃣ CHARTERS on October 17, 2023:")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, pickup_time, total_amount_due, 
           paid_amount, client_id, booking_notes, notes, driver_name
    FROM charters
    WHERE DATE(charter_date) = '2023-10-17'
    ORDER BY charter_date
""")

oct17 = cur.fetchall()
print(f"Found {len(oct17)} charters on that day\n")
for c in oct17:
    cid, reserve, date, time, total, paid, client_id, booking, notes, driver = c
    paid_amt = paid if paid else 0
    print(f"Charter {cid:6d} | {reserve:8s} | Time: {time} | ${total:10.2f} | Paid: ${paid_amt:10.2f}")
    
    # Get client
    cur.execute("SELECT client_name FROM clients WHERE client_id = %s", (client_id,))
    client = cur.fetchone()
    if client:
        print(f"  Client: {client[0]}")
    
    print(f"  Driver: {driver}")
    
    if booking:
        print(f"  Booking: {booking[:100]}")
    if notes:
        print(f"  Notes: {notes[:100]}")
    print()

# Search specifically for Blue Cross references
print("\n\n2️⃣ CHARTERS mentioning 'BLUE CROSS':")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due,
           booking_notes, notes, client_id
    FROM charters
    WHERE booking_notes ILIKE '%blue cross%'
    OR notes ILIKE '%blue cross%'
    ORDER BY charter_date DESC
    LIMIT 30
""")

blue_cross = cur.fetchall()
print(f"Found {len(blue_cross)} charters\n")
for c in blue_cross[:20]:
    cid, reserve, date, total, booking, notes, client_id = c
    print(f"Charter {cid:6d} | {reserve:8s} | {date} | ${total:10.2f}")
    if booking:
        print(f"  Booking: {booking[:100]}")
    if notes:
        print(f"  Notes: {notes[:100]}")
    print()

# Search for refund context
print("\n\n3️⃣ CHARTERS mentioning 'REFUND':")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due,
           booking_notes, notes, client_id
    FROM charters
    WHERE booking_notes ILIKE '%refund%'
    OR notes ILIKE '%refund%'
    ORDER BY charter_date DESC
    LIMIT 30
""")

refunds = cur.fetchall()
print(f"Found {len(refunds)} charters\n")
for c in refunds[:20]:
    cid, reserve, date, total, booking, notes, client_id = c
    print(f"Charter {cid:6d} | {reserve:8s} | {date} | ${total:10.2f}")
    if booking:
        print(f"  Booking: {booking[:100]}")
    if notes:
        print(f"  Notes: {notes[:100]}")
    print()

# Search Oct 2023 for Blue Cross + David + refund
print("\n\n4️⃣ OCT 2023 with BLUE CROSS + DAVID or REFUND:")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due,
           booking_notes, notes, client_id
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) = 2023
    AND EXTRACT(MONTH FROM charter_date) = 10
    AND (
        (booking_notes ILIKE '%blue cross%' OR notes ILIKE '%blue cross%')
        OR (booking_notes ILIKE '%david%' AND booking_notes ILIKE '%refund%')
        OR (notes ILIKE '%david%' AND notes ILIKE '%refund%')
    )
    ORDER BY charter_date DESC
    LIMIT 30
""")

oct_bc = cur.fetchall()
print(f"Found {len(oct_bc)} matches\n")
for c in oct_bc:
    cid, reserve, date, total, booking, notes, client_id = c
    print(f"Charter {cid:6d} | {reserve:8s} | {date} | ${total:10.2f}")
    if booking:
        print(f"  Booking: {booking[:100]}")
    if notes:
        print(f"  Notes: {notes[:100]}")

cur.close()
conn.close()
