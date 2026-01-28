#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    user='postgres',
    password='***REMOVED***',
    dbname='almsdata'
)
cur = conn.cursor()
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name='employees' 
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(row[0])
cur.close()
conn.close()
