import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("Looking for: DAVID RICHARD, medical appointment, Calgary, $600 e-transfer\n")
print("Analysis of findings so far:\n")

print("E-TRANSFER TRANSACTION:")
print("  Trans ID: 26349")
print("  Date: 2024-09-26")
print("  Amount: $600.00 (DEBIT - money out to David Richard)")
print("  Type: E-transfer TO David Richard")
print()

# This is an OUTGOING payment TO David Richard
# So David Richard is an EMPLOYEE/CONTRACTOR, not a customer
# The $600 was likely:
# 1. Reimbursement for a charter he booked for himself
# 2. Or direct payment for a trip/service

# Let me search for charters around Sept 26, 2024 involving David Richard
print("SEARCH: Charters around Sept 26, 2024:")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due, paid_amount,
           notes, booking_notes, client_id
    FROM charters
    WHERE charter_date BETWEEN '2024-09-20' AND '2024-10-05'
    AND (
        notes ILIKE '%david%'
        OR notes ILIKE '%calgary%'
        OR notes ILIKE '%medical%'
        OR booking_notes ILIKE '%david%'
        OR booking_notes ILIKE '%calgary%'
        OR booking_notes ILIKE '%medical%'
    )
    ORDER BY charter_date DESC
""")

charters = cur.fetchall()
print(f"Found {len(charters)} charters\n")
for c in charters:
    charter_id, reserve, date, total, paid, notes, booking_notes, client_id = c
    print(f"Charter {charter_id:6d} | {reserve:8s} | {date} | ${total:8.2f}")
    if notes:
        print(f"  Notes: {notes[:120]}")
    if booking_notes:
        print(f"  Booking: {booking_notes[:120]}")
    print()

# Also search for ANY charter around $600 in Sept 2024
print("\n\nSEARCH: All charters ~$600 in Sept 2024:")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due, paid_amount,
           client_id, notes
    FROM charters
    WHERE charter_date BETWEEN '2024-09-01' AND '2024-09-30'
    AND total_amount_due BETWEEN 580 AND 620
    ORDER BY charter_date DESC
""")

charters_600 = cur.fetchall()
print(f"Found {len(charters_600)} charters\n")
for c in charters_600[:20]:
    charter_id, reserve, date, total, paid, client_id, notes = c
    
    # Get client name
    cur.execute("SELECT client_name FROM clients WHERE client_id = %s", (client_id,))
    client_name_result = cur.fetchone()
    client_name = client_name_result[0] if client_name_result else f"ID {client_id}"
    
    print(f"Charter {charter_id:6d} | {reserve:8s} | {date} | ${total:8.2f} | Client: {client_name[:40]}")

cur.close()
conn.close()
