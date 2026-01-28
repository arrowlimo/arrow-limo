import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("Checking Charter 17714 in detail:\n")

# Get full charter details
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, client_id, 
           pickup_address, dropoff_address, total_amount_due, paid_amount,
           payment_status, booking_notes, notes, driver_name, driver_notes
    FROM charters
    WHERE charter_id = 17714
""")

charter = cur.fetchone()
if charter:
    charter_id, reserve, date, client_id, pickup, dropoff, total, paid, payment_status, booking_notes, notes, driver, driver_notes = charter
    
    print(f"Charter {charter_id} | Reserve {reserve}")
    print(f"Date: {date}")
    print(f"Client ID: {client_id}")
    paid_amt = paid if paid else 0
    print(f"Total: ${total:.2f} | Paid: ${paid_amt:.2f}")
    print(f"Payment Status: {payment_status}")
    print(f"Driver: {driver}")
    print()
    
    print("PICKUP:")
    print(f"  {pickup}")
    print()
    
    print("DROPOFF:")
    print(f"  {dropoff}")
    print()
    
    if booking_notes:
        print("BOOKING NOTES:")
        print(f"  {booking_notes[:300]}")
        print()
    
    if notes:
        print("NOTES:")
        print(f"  {notes}")
        print()
    
    if driver_notes:
        print("DRIVER NOTES:")
        print(f"  {driver_notes}")
        print()
    
    # Get client name
    cur.execute("SELECT client_name, company_name FROM clients WHERE client_id = %s", (client_id,))
    client = cur.fetchone()
    if client:
        cname, cname = client
        print(f"CLIENT: {cname} | {cname}")
    
    # Get payments for this charter
    print("\n\nPAYMENTS FOR THIS CHARTER:")
    print("-" * 100)
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date, payment_method, status, notes
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date DESC
    """, (reserve,))
    
    payments = cur.fetchall()
    print(f"Found {len(payments)} payments\n")
    for p in payments:
        p_id, p_reserve, p_amount, p_date, p_method, p_status, p_notes = p
        print(f"Payment {p_id:6d} | {p_date} | ${p_amount:8.2f} | {p_method}")
        if p_notes:
            print(f"  Notes: {p_notes[:80]}")
    
    # Search for linked e-transfer
    print("\n\nBanking transactions around this date:")
    print("-" * 100)
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount, 
               description, reconciled_payment_id
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
        AND (
            credit_amount BETWEEN %s AND %s
            OR debit_amount BETWEEN %s AND %s
        )
        ORDER BY transaction_date DESC
    """, (date - __import__('datetime').timedelta(days=5), date + __import__('datetime').timedelta(days=5),
          total - 50, total + 50, total - 50, total + 50))
    
    trans = cur.fetchall()
    print(f"Found {len(trans)} nearby transactions\n")
    for t in trans[:10]:
        t_id, t_date, credit, debit, desc, rec_id = t
        amount = credit if credit else debit
        print(f"Trans {t_id:8d} | {t_date} | ${amount:8.2f} | {desc[:70]}")

else:
    print("Charter not found!")

cur.close()
conn.close()
