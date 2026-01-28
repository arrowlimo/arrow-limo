import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("=== PAYMENTS TABLE STRUCTURE ===")
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='payments' AND column_name LIKE '%square%' ORDER BY ordinal_position")
for row in cur.fetchall():
    print(f"  {row[0]:30s} {row[1]}")

print("\n=== SQUARE PAYMENT TRACKING ===")
cur.execute("""
    SELECT 
        COUNT(*) as total_payments,
        COUNT(square_transaction_id) as with_square_txn_id,
        COUNT(DISTINCT square_transaction_id) as unique_square_txn,
        COUNT(square_payment_id) as with_square_pay_id,
        COUNT(square_customer_email) as with_square_email
    FROM payments
""")
result = cur.fetchone()
print(f"Total payments: {result[0]:,}")
print(f"With square_transaction_id: {result[1]:,}")
print(f"Unique square_transaction_id: {result[2]:,}")
print(f"With square_payment_id: {result[3]:,}")
print(f"With square_customer_email: {result[4]:,}")

print("\n=== EMAIL FINANCIAL EVENTS (Square receipts) ===")
cur.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'email_financial_events'
    )
""")
if cur.fetchone()[0]:
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE event_type ILIKE '%square%') as square_events,
            COUNT(*) FILTER (WHERE matched_payment_id IS NOT NULL) as matched_to_payment
        FROM email_financial_events
    """)
    result = cur.fetchone()
    print(f"Total email events: {result[0]:,}")
    print(f"Square events: {result[1]:,}")
    print(f"Matched to payments: {result[2]:,}")
else:
    print("email_financial_events table not found")

print("\n=== SAMPLE SQUARE PAYMENT ===")
cur.execute("""
    SELECT 
        payment_id, reserve_number, amount, payment_date,
        payment_method, square_transaction_id, square_payment_id,
        square_customer_email, notes
    FROM payments
    WHERE square_transaction_id IS NOT NULL
    LIMIT 3
""")
for row in cur.fetchall():
    print(f"\nPayment {row[0]} (Rsv {row[1]}):")
    print(f"  Amount: ${row[2]:.2f} on {row[3]}")
    print(f"  Method: {row[4]}")
    print(f"  Square TXN: {row[5]}")
    print(f"  Square PAY: {row[6]}")
    print(f"  Email: {row[7]}")
    print(f"  Notes: {row[8]}")

conn.close()
