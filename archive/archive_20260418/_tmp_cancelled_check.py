import psycopg2
conn = psycopg2.connect(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")
cur = conn.cursor()
cur.execute("""
    SELECT cancelled, status, COUNT(*)
    FROM charters
    WHERE charter_date BETWEEN '2012-01-01' AND '2012-12-31'
    GROUP BY cancelled, status
    ORDER BY COUNT(*) DESC
""")
for r in cur.fetchall():
    print(r)
conn.close()
