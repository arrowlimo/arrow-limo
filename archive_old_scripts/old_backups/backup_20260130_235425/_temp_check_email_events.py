import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("=== EMAIL_FINANCIAL_EVENTS TABLE ===")
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='email_financial_events' ORDER BY ordinal_position")
for row in cur.fetchall():
    print(f"  {row[0]:30s} {row[1]}")

print("\n=== EMAIL EVENTS SUMMARY ===")
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE event_type ILIKE '%square%') as square_events,
        COUNT(*) FILTER (WHERE reserve_number IS NOT NULL) as with_reserve,
        COUNT(*) FILTER (WHERE reserve_number IS NOT NULL) as with_charter
    FROM email_financial_events
""")
result = cur.fetchone()
print(f"Total email events: {result[0]:,}")
print(f"Square events: {result[1]:,}")
print(f"With reserve_number: {result[2]:,}")
print(f"With charter_id: {result[3]:,}")

print("\n=== SAMPLE SQUARE EMAIL EVENT ===")
cur.execute("""
    SELECT id, event_date, event_type, amount, customer_name, reserve_number, transaction_reference
    FROM email_financial_events
    WHERE event_type ILIKE '%square%'
    ORDER BY event_date DESC
    LIMIT 3
""")
for row in cur.fetchall():
    print(f"\nEvent {row[0]}: {row[2]}")
    print(f"  Date: {row[1]}, Amount: ${row[3]:.2f}")
    print(f"  Customer: {row[4]}")
    print(f"  Reserve: {row[5]}, Ref: {row[6]}")

conn.close()
