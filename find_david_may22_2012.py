import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("Searching for: DAVID RICHARD + MEDICAL + CALGARY + ~$600 on May 22, 2012\n")

# Search for charters around May 22, 2012
print("1️⃣ CHARTERS on May 22, 2012 around $600:")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due, paid_amount,
           pickup_address, dropoff_address, booking_notes, notes, client_id
    FROM charters
    WHERE DATE(charter_date) = '2012-05-22'
    AND total_amount_due BETWEEN 550 AND 650
    ORDER BY charter_date DESC
""")

results = cur.fetchall()
print(f"Found {len(results)} charters on that date around $600\n")
for r in results:
    cid, reserve, date, total, paid, pickup, dropoff, booking, notes, client_id = r
    paid_amt = paid if paid else 0
    print(f"Charter {cid:6d} | Reserve {reserve:8s} | ${total:10.2f} | Paid: ${paid_amt:10.2f}")
    if pickup:
        print(f"  Pickup: {pickup[:70]}")
    if dropoff:
        print(f"  Dropoff: {dropoff[:70]}")
    if booking:
        print(f"  Booking: {booking[:100]}")
    if notes:
        print(f"  Notes: {notes[:100]}")
    
    # Get client name
    cur.execute("SELECT client_name FROM clients WHERE client_id = %s", (client_id,))
    client_result = cur.fetchone()
    if client_result:
        print(f"  Client: {client_result[0]}")
    print()

# Search 2: Any charter on that date mentioning David
print("\n2️⃣ ALL CHARTERS on May 22, 2012:")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, total_amount_due, booking_notes, notes
    FROM charters
    WHERE DATE(charter_date) = '2012-05-22'
    ORDER BY total_amount_due DESC
""")

all_charters = cur.fetchall()
print(f"Found {len(all_charters)} charters that day\n")
for c in all_charters:
    cid, reserve, total, booking, notes = c
    print(f"Charter {cid:6d} | {reserve:8s} | ${total:10.2f}")
    if booking and len(booking) < 200:
        print(f"  {booking}")
    if notes and len(notes) < 200:
        print(f"  {notes}")

# Search 3: Check May 2012 broadly for David Richard medical Calgary
print("\n\n3️⃣ ENTIRE MAY 2012 with DAVID + MEDICAL + CALGARY:")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due,
           booking_notes, notes
    FROM charters
    WHERE DATE_TRUNC('month', charter_date) = '2012-05-01'::date
    AND (
        (notes ILIKE '%david%' AND notes ILIKE '%medical%' AND notes ILIKE '%calgary%')
        OR (booking_notes ILIKE '%david%' AND booking_notes ILIKE '%medical%' AND booking_notes ILIKE '%calgary%')
    )
    ORDER BY charter_date DESC
""")

may_charters = cur.fetchall()
print(f"Found {len(may_charters)} matches\n")
for c in may_charters:
    cid, reserve, date, total, booking, notes = c
    print(f"Charter {cid:6d} | {reserve:8s} | {date} | ${total:10.2f}")
    if notes:
        print(f"  Notes: {notes[:120]}")

# Search 4: May 2012 charters with Calgary destination and ~$600
print("\n\n4️⃣ MAY 2012 CHARTERS to CALGARY ~$600:")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due,
           dropoff_address, booking_notes, notes
    FROM charters
    WHERE DATE_TRUNC('month', charter_date) = '2012-05-01'::date
    AND total_amount_due BETWEEN 550 AND 650
    AND (dropoff_address ILIKE '%calgary%' OR notes ILIKE '%calgary%' OR booking_notes ILIKE '%calgary%')
    ORDER BY charter_date DESC
""")

calgary_charters = cur.fetchall()
print(f"Found {len(calgary_charters)} charters\n")
for c in calgary_charters:
    cid, reserve, date, total, dropoff, booking, notes = c
    print(f"Charter {cid:6d} | {reserve:8s} | {date} | ${total:10.2f}")
    if dropoff:
        print(f"  Dropoff: {dropoff[:80]}")
    if notes:
        print(f"  Notes: {notes[:100]}")

cur.close()
conn.close()
