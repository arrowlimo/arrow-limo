import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# The key insight: David Richard e-transfer on Sept 26, 2024 is $600
# This could be:
# 1. Reimbursement TO David Richard from a customer charter
# 2. OR payment FROM David Richard's charter

# Let me search for charters by checking booking notes more carefully
print("Search approach: Finding charter with 'Calgary' + Medical context + David Richard:")
print("=" * 100)

# Maybe David Richard is the CLIENT who booked it
# Or David Richard is referenced in the booking notes

# Try searching around the September 2024 timeframe more broadly
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due, 
           booking_notes, client_id
    FROM charters
    WHERE charter_date BETWEEN '2024-08-26' AND '2024-10-15'
    ORDER BY charter_date DESC
    LIMIT 50
""")

charters = cur.fetchall()
print(f"Found {len(charters)} charters in late Sept 2024:\n")

target_charters = []
for c in charters:
    cid, reserve, date, total, booking, cid_val = c
    # Check if booking notes suggest medical or David Richard
    if booking:
        booking_lower = booking.lower()
        if ("calgary" in booking_lower or "medical" in booking_lower or 
            "doctor" in booking_lower or "appointment" in booking_lower or
            "david" in booking_lower):
            target_charters.append((cid, reserve, date, total, booking))
            print(f"✅ Charter {cid:6d} | {reserve:8s} | {date} | ${total:8.2f}")
            print(f"   {booking[:150]}")
            print()

if not target_charters:
    print("No specific medical/David/Calgary charters found in that period")
    print("\nLet me try: Charters EXACTLY $600:")
    
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date, total_amount_due,
               booking_notes
        FROM charters
        WHERE total_amount_due = 600.00
        ORDER BY charter_date DESC
        LIMIT 10
    """)
    
    for cid, reserve, date, total, booking in cur.fetchall():
        print(f"Charter {cid:6d} | {reserve:8s} | {date} | ${total:8.2f}")
        if booking:
            print(f"  {booking[:100]}")

cur.close()
conn.close()
