"""Check if the 'doubled' payments actually have different payment_date values."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Check the sample reserves from the analysis
reserves = ['006232', '010145', '014685', '014766', '019244', '010146', '019037', '015840']

for reserve in reserves:
    cur.execute("""
        SELECT payment_id, amount, payment_date, payment_key, created_at
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_id
    """, (reserve,))
    
    payments = cur.fetchall()
    print(f"\nReserve {reserve}: {len(payments)} payments")
    for p in payments:
        print(f"  ID {p[0]}: ${p[1]:,.2f} on {p[2]}, Key: {p[3]}, Created: {p[4]}")
    
    # Check if they match on date
    if len(payments) >= 2:
        dates = [p[2] for p in payments]
        if len(set(dates)) == 1:
            print(f"  → Same payment_date: TRUE DUPLICATE")
        else:
            print(f"  → Different payment_dates: DATA QUALITY ISSUE")

cur.close()
conn.close()
