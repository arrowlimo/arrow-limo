#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect('host=ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech dbname=neondb user=neondb_owner password=npg_89MbcFmZwUWo sslmode=require')
cur = conn.cursor()

# Get all charter columns
cur.execute("""
SELECT column_name FROM information_schema.columns 
WHERE table_name='charters' 
ORDER BY ordinal_position
LIMIT 20
""")

print("First 20 columns in charters table:")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.close()
conn.close()
