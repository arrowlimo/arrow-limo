import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("Searching for DAVID RICHARD medical appointment Calgary $600 charter...\n")

# Search in charters
print("1️⃣ CHARTERS with medical/Calgary reference:")
print("-" * 100)
cur.execute("""
    SELECT charter_id, reserve_number, client_id, charter_date, dropoff_address,
           booking_notes, total_amount_due, paid_amount, status, notes
    FROM charters
    WHERE (notes ILIKE '%DAVID RICHARD%' OR notes ILIKE '%medical%' OR notes ILIKE '%Calgary%')
    OR (dropoff_address ILIKE '%Calgary%' AND (booking_notes ILIKE '%medical%' OR notes ILIKE '%medical%'))
    OR (booking_notes ILIKE '%medical%' AND dropoff_address ILIKE '%Calgary%')
    ORDER BY charter_date DESC
    LIMIT 20
""")

charters = cur.fetchall()
print(f"Found {len(charters)} charters with medical/Calgary reference\n")
for c in charters:
    charter_id, reserve, client_id, date, dropoff, booking_notes, total, paid, status, notes = c
    print(f"Charter {charter_id:6d} | Reserve {reserve:8s} | ${total:10.2f} | {date} | Status: {status}")
    print(f"  Dropoff: {dropoff}")
    print(f"  Booking: {booking_notes}")
    if notes:
        print(f"  Notes: {notes[:100]}")
    print()

# Search in banking transactions for DAVID RICHARD $600 e-transfer
print("\n2️⃣ BANKING ETRANSFERS from/to DAVID RICHARD around $600:")
print("-" * 100)
cur.execute("""
    SELECT transaction_id, transaction_date, credit_amount, debit_amount, description
    FROM banking_transactions
    WHERE description ILIKE '%DAVID RICHARD%'
    AND (
        (credit_amount BETWEEN 550 AND 650)
        OR (debit_amount BETWEEN 550 AND 650)
    )
    ORDER BY transaction_date DESC
    LIMIT 20
""")

trans = cur.fetchall()
print(f"Found {len(trans)} banking transactions\n")
for t in trans:
    trans_id, date, credit, debit, desc = t
    amount = credit if credit else debit
    trans_type = 'CREDIT' if credit else 'DEBIT'
    print(f"Trans {trans_id:8d} | {date} | ${amount:10.2f} ({trans_type}) | {desc[:80]}")

# Search for payments linked to DAVID RICHARD
print("\n3️⃣ PAYMENTS with DAVID RICHARD reference:")
print("-" * 100)
cur.execute("""
    SELECT payment_id, reserve_number, amount, payment_date, payment_method, status, notes
    FROM payments
    WHERE (notes ILIKE '%DAVID RICHARD%' OR reserve_number ILIKE '%DAVID%')
    AND (amount BETWEEN 550 AND 650)
    ORDER BY payment_date DESC
    LIMIT 20
""")

payments = cur.fetchall()
print(f"Found {len(payments)} payments\n")
for p in payments:
    pid, reserve, amount, date, method, status, notes = p
    print(f"Payment {pid:6d} | Reserve {reserve or 'NULL':10s} | ${amount:10.2f} | {date} | Method: {method}")
    if notes:
        print(f"  Notes: {notes[:100]}")
    print()

# Broader search: all DAVID RICHARD transactions
print("\n4️⃣ ALL DAVID RICHARD banking transactions (any amount):")
print("-" * 100)
cur.execute("""
    SELECT transaction_id, transaction_date, credit_amount, debit_amount, description
    FROM banking_transactions
    WHERE description ILIKE '%DAVID RICHARD%'
    OR description ILIKE '%D RICHARD%'
    ORDER BY transaction_date DESC
    LIMIT 30
""")

all_trans = cur.fetchall()
print(f"Found {len(all_trans)} total transactions\n")
for t in all_trans[:15]:
    trans_id, date, credit, debit, desc = t
    amount = credit if credit else debit
    print(f"Trans {trans_id:8d} | {date} | ${amount:10.2f} | {desc[:80]}")

cur.close()
conn.close()
