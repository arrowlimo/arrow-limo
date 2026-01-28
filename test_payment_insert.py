import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Try a simple insert
try:
    cur.execute("""
        INSERT INTO payments
        (reserve_number, amount, payment_date, payment_method, status, notes, created_at, updated_at)
        VALUES ('TEST_001', 100.00, '2025-01-20', 'bank_transfer', 'completed', 'Test', NOW(), NOW())
        RETURNING payment_id
    """)
    result = cur.fetchone()
    print(f"✅ INSERT successful: {result}")
    conn.rollback()  # Don't actually save
except Exception as e:
    print(f"❌ INSERT failed: {e}")

cur.close()
conn.close()
