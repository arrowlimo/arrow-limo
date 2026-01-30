import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

# Clear charter_payments for BDA
cur.execute("DELETE FROM charter_payments WHERE source = 'batch_deposit_allocation' OR payment_key LIKE 'BDA_%'")
deleted = cur.rowcount
print(f"Deleted {deleted:,} rows")

# Try simpler insert without JOINs
cur.execute("""
    SELECT COUNT(*) as count
    FROM batch_deposit_allocations
""")
bda_count = cur.fetchone()[0]
print(f"batch_deposit_allocations: {bda_count:,}")

# Insert one batch_deposit_allocation manually first
cur.execute("""
    SELECT bda.allocation_id, bda.reserve_number, bda.allocation_amount
    FROM batch_deposit_allocations bda
    LIMIT 1
""")
sample = cur.fetchone()
print(f"Sample: allocation_id={sample[0]}, reserve_number={sample[1]}, amount={sample[2]}")

# Now try inserting with explicit VALUES
cur.execute("""
    INSERT INTO charter_payments (charter_id, client_name, charter_date, payment_date, amount, payment_method, source, payment_key, imported_at)
    VALUES (%s, 'TEST', CURRENT_DATE, CURRENT_DATE, %s, 'credit_card', 'batch_deposit_allocation', %s, NOW())
""", (sample[1], sample[2], f"BDA_{sample[0]}"))

print(f"Inserted {cur.rowcount} rows")

# Now try the full INSERT
print("\nTrying full INSERT...")
cur.execute("""
    SELECT COUNT(*) FROM batch_deposit_allocations bda
    JOIN charters c ON c.reserve_number = bda.reserve_number
""")
expected = cur.fetchone()[0]
print(f"Expected rows (from SELECT): {expected:,}")

cur.execute("""
    INSERT INTO charter_payments (charter_id, client_name, charter_date, payment_date, amount, payment_method, source, payment_key, imported_at)
    SELECT 
        bda.reserve_number,
        c.client_display_name,
        c.charter_date,
        COALESCE(c.charter_date, CURRENT_DATE),
        bda.allocation_amount,
        'credit_card',
        'batch_deposit_allocation',
        'BDA_' || bda.allocation_id,
        NOW()
    FROM batch_deposit_allocations bda
    JOIN charters c ON c.reserve_number = bda.reserve_number
""")

print(f"Actually inserted: {cur.rowcount:,}")

conn.commit()
cur.close()
conn.close()
