import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("Searching comprehensively for medical appointment Calgary charter...\n")

# Search 1: Medical + Calgary in any field
print("1️⃣ CHARTERS with MEDICAL AND CALGARY (any amount):")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, client_id, charter_date, pickup_address, dropoff_address,
           total_amount_due, paid_amount, status, booking_notes, notes
    FROM charters
    WHERE (
        (notes ILIKE '%medical%' AND notes ILIKE '%calgary%')
        OR (booking_notes ILIKE '%medical%' AND booking_notes ILIKE '%calgary%')
        OR (dropoff_address ILIKE '%calgary%' AND (notes ILIKE '%medical%' OR notes ILIKE '%doctor%' OR notes ILIKE '%appointment%'))
        OR (pickup_address ILIKE '%calgary%' AND (notes ILIKE '%medical%' OR notes ILIKE '%doctor%' OR notes ILIKE '%appointment%'))
    )
    ORDER BY charter_date DESC
    LIMIT 30
""")

results = cur.fetchall()
print(f"Found {len(results)} matches\n")
for r in results:
    charter_id, reserve, client_id, date, pickup, dropoff, total, paid, status, booking_notes, notes = r
    print(f"Charter {charter_id:6d} | Reserve {reserve:8s} | ${total:10.2f} | {date}")
    print(f"  Status: {status}")
    print(f"  Pickup: {pickup[:60] if pickup else 'N/A'}")
    print(f"  Dropoff: {dropoff[:60] if dropoff else 'N/A'}")
    if notes:
        print(f"  Notes: {notes[:150]}")
    if booking_notes:
        print(f"  Booking: {booking_notes[:150]}")
    print()

# Search 2: "David" in any charter field with medical
print("\n\n2️⃣ CHARTERS with DAVID + MEDICAL:")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, client_id, charter_date, total_amount_due,
           pickup_address, dropoff_address, notes, booking_notes
    FROM charters
    WHERE (
        notes ILIKE '%david%'
        OR booking_notes ILIKE '%david%'
        OR pickup_address ILIKE '%david%'
        OR dropoff_address ILIKE '%david%'
    )
    AND (
        notes ILIKE '%medical%'
        OR booking_notes ILIKE '%medical%'
        OR notes ILIKE '%doctor%'
        OR notes ILIKE '%appointment%'
        OR notes ILIKE '%calgary%'
    )
    ORDER BY charter_date DESC
    LIMIT 30
""")

results2 = cur.fetchall()
print(f"Found {len(results2)} matches\n")
for r in results2[:20]:
    charter_id, reserve, client_id, date, total, pickup, dropoff, notes, booking_notes = r
    print(f"Charter {charter_id:6d} | Reserve {reserve:8s} | ${total:10.2f} | {date}")
    if notes:
        print(f"  Notes: {notes[:120]}")
    if booking_notes and len(booking_notes) < 200:
        print(f"  Booking: {booking_notes}")

# Search 3: Keyword search - "medical" anywhere in database
print("\n\n3️⃣ ANY CHARTER with 'MEDICAL' keyword:")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due, notes
    FROM charters
    WHERE notes ILIKE '%medical%'
    OR booking_notes ILIKE '%medical%'
    ORDER BY charter_date DESC
    LIMIT 20
""")

medical = cur.fetchall()
print(f"Found {len(medical)} charters with 'medical'\n")
for m in medical[:15]:
    charter_id, reserve, date, total, notes = m
    print(f"Charter {charter_id:6d} | Reserve {reserve:8s} | ${total:10.2f} | {date}")
    print(f"  {notes[:100] if notes else 'N/A'}")

cur.close()
conn.close()
