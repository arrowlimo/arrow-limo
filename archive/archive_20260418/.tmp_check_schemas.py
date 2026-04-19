#!/usr/bin/env python3
"""Check schema for charters and charter_payments tables"""
import psycopg2

conn = psycopg2.connect(
    host='localhost', port=5432, dbname='almsdata',
    user='postgres', password='ArrowLimousine'
)
cur = conn.cursor()

# Check charters schema
print("CHARTERS TABLE SCHEMA:")
cur.execute("""
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'charters'
ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"  {row[0]:25} {row[1]:20} nullable={row[2]}")

# Check charter_payments schema
print("\nCHARTER_PAYMENTS TABLE SCHEMA:")
cur.execute("""
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'charter_payments'
ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"  {row[0]:25} {row[1]:20} nullable={row[2]}")

# Check payments schema
print("\nPAYMENTS TABLE SCHEMA:")
cur.execute("""
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'payments'
ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"  {row[0]:25} {row[1]:20} nullable={row[2]}")

conn.close()
