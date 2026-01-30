import psycopg2

c = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = c.cursor()

cur.execute('''
    SELECT 
        reserve_number, 
        charter_date, 
        total_amount_due, 
        paid_amount, 
        balance, 
        status, 
        cancelled
    FROM charters 
    WHERE client_id = 2311 
    AND ABS(total_amount_due - 774.00) < 0.01 
    AND balance > 0 
    ORDER BY charter_date
''')

print("Unpaid Waste Connections $774 charters:\n")
for reserve, date, due, paid, balance, status, cancelled in cur.fetchall():
    print(f"Reserve: {reserve}")
    print(f"  Date: {date}")
    print(f"  Due: ${float(due):.2f}")
    print(f"  Paid: ${float(paid):.2f}")
    print(f"  Balance: ${float(balance):.2f}")
    print(f"  Status: {status}, Cancelled: {cancelled}")
    
    # Check if payments exist for this reserve
    cur.execute('''
        SELECT payment_id, payment_date, amount, payment_key
        FROM payments
        WHERE reserve_number = %s
    ''', (reserve,))
    payments = cur.fetchall()
    if payments:
        print(f"  Payments found: {len(payments)}")
        for pid, pdate, amt, key in payments:
            print(f"    Payment {pid}: ${float(amt):.2f} on {pdate}, key={key or 'NULL'}")
    else:
        print(f"  No payments found")
    print()
