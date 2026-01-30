"""Find all employee-related tables"""
import psycopg2
import os

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema='public' 
    AND (table_name LIKE '%employee%' 
         OR table_name LIKE '%training%' 
         OR table_name LIKE '%payroll%' 
         OR table_name LIKE '%advance%'
         OR table_name LIKE '%driver%')
    ORDER BY table_name
""")

print("Employee-related tables:")
for row in cur.fetchall():
    print(f"  - {row[0]}")

cur.close()
conn.close()
