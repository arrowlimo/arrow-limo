import psycopg2

conn = psycopg2.connect(
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***',
    host='localhost'
)
cur = conn.cursor()

print("Recalculating charter paid_amount and balance using reserve_number...")

cur.execute("""
    WITH payment_sums AS (
        SELECT 
            reserve_number,
            ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as actual_paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    UPDATE charters c
    SET paid_amount = ps.actual_paid,
        balance = c.total_amount_due - ps.actual_paid
    FROM payment_sums ps
    WHERE c.reserve_number = ps.reserve_number
""")
updated = cur.rowcount
print(f"✓ Updated from payment sums: {updated} charters")

cur.execute("""
    UPDATE charters c
    SET paid_amount = 0,
        balance = c.total_amount_due
    WHERE c.reserve_number IS NOT NULL
      AND NOT EXISTS (
        SELECT 1 FROM payments p 
        WHERE p.reserve_number = c.reserve_number
      )
""")
zeroed = cur.rowcount
print(f"✓ Zeroed with no payments: {zeroed} charters")

conn.commit()
print("✓ Commit complete")

cur.close()
conn.close()
