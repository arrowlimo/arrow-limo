#!/usr/bin/env python3
import psycopg2

conn=psycopg2.connect(host='localhost',database='almsdata',user='postgres',password='***REMOVED***')
cur=conn.cursor()
cur.execute("""
    SELECT column_name FROM information_schema.columns WHERE table_name='vehicles' ORDER BY column_name
""")
print([r[0] for r in cur.fetchall()])
cur.close(); conn.close()
