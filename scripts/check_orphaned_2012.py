"""Quick check of orphaned 2012 payments - revenue vs refunds/expenses"""
import psycopg2, os
from datetime import date

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'), 
    dbname=os.getenv('DB_NAME','almsdata'), 
    user=os.getenv('DB_USER','postgres'), 
    password=os.getenv('DB_PASSWORD','***REMOVED***')
)
cur = conn.cursor()

s, e = date(2012,1,1), date(2013,1,1)

# Overall stats
cur.execute("""
    SELECT 
        COUNT(*), 
        COALESCE(SUM(amount),0), 
        COALESCE(SUM(amount) FILTER (WHERE amount > 0), 0) as positive_sum,
        COALESCE(SUM(amount) FILTER (WHERE amount < 0), 0) as negative_sum,
        COUNT(*) FILTER (WHERE amount > 0) as positive_count,
        COUNT(*) FILTER (WHERE amount < 0) as negative_count,
        MIN(amount), 
        MAX(amount)
    FROM payments 
    WHERE payment_date >= %s AND payment_date < %s 
      AND reserve_number IS NULL
""", (s, e))

r = cur.fetchone()
print(f"=== Orphaned 2012 Payments (no reserve_number) ===")
print(f"Total: {r[0]} payments")
print(f"Net amount: ${r[1]:,.2f}")
print(f"Positive (revenue): {r[4]} payments, ${r[2]:,.2f}")
print(f"Negative (refunds/reversals): {r[5]} payments, ${r[3]:,.2f}")
print(f"Range: ${r[6]:,.2f} to ${r[7]:,.2f}")

# Sample positive (revenue received)
print(f"\n=== Sample 10 Positive (Revenue) ===")
cur.execute("""
    SELECT payment_id, payment_date, amount, payment_method, 
           COALESCE(LEFT(notes, 50), 'NO NOTES')
    FROM payments 
    WHERE payment_date >= %s AND payment_date < %s 
      AND reserve_number IS NULL 
      AND amount > 0
    ORDER BY amount DESC
    LIMIT 10
""", (s, e))

for row in cur.fetchall():
    print(f"${row[2]:>8,.2f} | {row[1]} | {row[3] or 'NULL':15} | {row[4]}")

# Sample negative (refunds/reversals)
print(f"\n=== Sample 10 Negative (Refunds/Reversals) ===")
cur.execute("""
    SELECT payment_id, payment_date, amount, payment_method, 
           COALESCE(LEFT(notes, 50), 'NO NOTES')
    FROM payments 
    WHERE payment_date >= %s AND payment_date < %s 
      AND reserve_number IS NULL 
      AND amount < 0
    ORDER BY amount ASC
    LIMIT 10
""", (s, e))

negs = cur.fetchall()
if negs:
    for row in negs:
        print(f"${row[2]:>8,.2f} | {row[1]} | {row[3] or 'NULL':15} | {row[4]}")
else:
    print("(None)")

cur.close()
conn.close()
