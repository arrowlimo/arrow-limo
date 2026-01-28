import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("Searching for medical appointment charter in Calgary...\n")

# Get DAVID RICHARD's client record first
print("1️⃣ DAVID RICHARD as CLIENT:")
print("-" * 100)
cur.execute("""
    SELECT client_id, client_name, company_name, email
    FROM clients
    WHERE client_name ILIKE '%DAVID RICHARD%'
    OR company_name ILIKE '%DAVID RICHARD%'
""")

clients = cur.fetchall()
print(f"Found {len(clients)} client records\n")
for cid, cname, cname, email in clients:
    print(f"Client {cid:6d} | {cname:40s} | {cname}")

# Now search for charters with medical appointment around $600
print("\n\n2️⃣ CHARTERS with MEDICAL or $600:")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, client_id, charter_date, dropoff_address,
           booking_notes, total_amount_due, paid_amount, status, notes
    FROM charters
    WHERE (total_amount_due BETWEEN 580 AND 620)
    AND (
        booking_notes ILIKE '%medical%'
        OR notes ILIKE '%medical%'
        OR notes ILIKE '%doctor%'
        OR notes ILIKE '%appointment%'
        OR notes ILIKE '%Calgary%'
        OR dropoff_address ILIKE '%Calgary%'
    )
    ORDER BY charter_date DESC
    LIMIT 30
""")

charters = cur.fetchall()
print(f"Found {len(charters)} charters around $600 with medical keywords\n")
for c in charters[:20]:
    charter_id, reserve, client_id, date, dropoff, booking_notes, total, paid, status, notes = c
    print(f"Charter {charter_id:6d} | Reserve {reserve:8s} | ${total:10.2f} | {date}")
    print(f"  Status: {status} | Dropoff: {dropoff[:50] if dropoff else 'N/A'}")
    if booking_notes:
        print(f"  Booking: {booking_notes[:80]}")
    if notes:
        print(f"  Notes: {notes[:100]}")
    print()

# Also search for any charter with exact $600
print("\n\n3️⃣ ALL CHARTERS with EXACTLY $600:")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, client_id, charter_date, dropoff_address,
           booking_notes, total_amount_due, paid_amount, status
    FROM charters
    WHERE total_amount_due = 600.00
    ORDER BY charter_date DESC
    LIMIT 20
""")

charters_600 = cur.fetchall()
print(f"Found {len(charters_600)} charters with exactly $600\n")
for c in charters_600:
    charter_id, reserve, client_id, date, dropoff, booking_notes, total, paid, status = c
    print(f"Charter {charter_id:6d} | Reserve {reserve:8s} | {date} | Status: {status}")
    print(f"  Client {client_id} | Dropoff: {dropoff[:60] if dropoff else 'N/A'}")
    if booking_notes:
        print(f"  Booking: {booking_notes[:80]}")

# Get the actual client name for these charters
if charters_600:
    print("\n\n4️⃣ CLIENT DETAILS FOR $600 CHARTERS:")
    print("-" * 100)
    client_ids = [c[2] for c in charters_600]
    placeholders = ','.join(['%s'] * len(client_ids))
    
    cur.execute(f"""
        SELECT DISTINCT c.client_id, c.client_name, c.company_name
        FROM clients c
        WHERE c.client_id IN ({placeholders})
    """, client_ids)
    
    for cid, cname, cname in cur.fetchall():
        print(f"Client {cid:6d}: {cname:40s} | {cname}")

cur.close()
conn.close()
