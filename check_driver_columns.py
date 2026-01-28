import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()
cur.execute("""
    SELECT reserve_number, driver, driver_name 
    FROM charters 
    WHERE reserve_number IN ('007032', '006990', '007042')
    ORDER BY reserve_number
""")

print("Reserve# | driver       | driver_name")
print("-" * 50)
for row in cur.fetchall():
    print(f"{row[0]:8} | {row[1] or 'NULL':12} | {row[2] or 'NULL'}")

cur.close()
conn.close()
