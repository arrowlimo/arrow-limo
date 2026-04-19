import psycopg2
conn = psycopg2.connect(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")
cur = conn.cursor()

# Max payments per charter in 2012
cur.execute("""
    SELECT MAX(cnt) FROM (
        SELECT cp.charter_id, COUNT(*) as cnt
        FROM charter_payments cp
        WHERE cp.charter_date BETWEEN '2012-01-01' AND '2012-12-31'
        GROUP BY cp.charter_id
    ) sub
""")
print("Max payments per charter:", cur.fetchone()[0])

# Distribution of payment counts
cur.execute("""
    SELECT cnt, COUNT(*) as charters
    FROM (
        SELECT cp.charter_id, COUNT(*) as cnt
        FROM charter_payments cp
        WHERE cp.charter_date BETWEEN '2012-01-01' AND '2012-12-31'
        GROUP BY cp.charter_id
    ) sub
    GROUP BY cnt ORDER BY cnt
""")
print("Payment count distribution:")
for r in cur.fetchall():
    print(f"  {r[0]} payments: {r[1]} charters")

# Check a charter with multiple payments
cur.execute("""
    SELECT cp.charter_id, cp.amount, cp.payment_date, cp.payment_method, cp.payment_key
    FROM charter_payments cp
    WHERE cp.charter_date BETWEEN '2012-01-01' AND '2012-12-31'
    AND cp.charter_id IN (
        SELECT charter_id FROM charter_payments 
        WHERE charter_date BETWEEN '2012-01-01' AND '2012-12-31'
        GROUP BY charter_id HAVING COUNT(*) >= 3 LIMIT 3
    )
    ORDER BY cp.charter_id, cp.payment_date
""")
print("\nSample multi-payment charters:")
for r in cur.fetchall():
    print(r)

# How does charter_payments.charter_id link to charters.charter_id?
cur.execute("""
    SELECT cp.charter_id, c.charter_id as c_id, c.reserve_number
    FROM charter_payments cp
    LEFT JOIN charters c ON c.reserve_number = cp.charter_id
    WHERE cp.charter_date BETWEEN '2012-01-01' AND '2012-12-31'
    LIMIT 5
""")
print("\nPayment to charter link via reserve_number:")
for r in cur.fetchall():
    print(r)

conn.close()
