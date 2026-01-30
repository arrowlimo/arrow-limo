#!/usr/bin/env python3
"""Check receipts and invoices schema for category vs GL code fields."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()

print("=" * 80)
print("RECEIPTS TABLE SCHEMA")
print("=" * 80)
cur.execute("""
    SELECT column_name, data_type, character_maximum_length 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"{row[0]:30} {row[1]:20} {row[2] if row[2] else ''}")

print("\n" + "=" * 80)
print("INVOICES TABLE SCHEMA")
print("=" * 80)
cur.execute("""
    SELECT column_name, data_type, character_maximum_length 
    FROM information_schema.columns 
    WHERE table_name = 'invoices' 
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"{row[0]:30} {row[1]:20} {row[2] if row[2] else ''}")

print("\n" + "=" * 80)
print("CHECK FOR CATEGORY FIELDS IN RECEIPTS")
print("=" * 80)
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    AND column_name LIKE '%category%'
""")
category_cols = cur.fetchall()
if category_cols:
    print("Category columns found:", [c[0] for c in category_cols])
else:
    print("No category columns found")

print("\n" + "=" * 80)
print("CHECK FOR GL CODE/ACCOUNT FIELDS IN RECEIPTS")
print("=" * 80)
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    AND (column_name LIKE '%gl%' OR column_name LIKE '%account%')
""")
gl_cols = cur.fetchall()
if gl_cols:
    print("GL/Account columns found:", [c[0] for c in gl_cols])
else:
    print("No GL/Account columns found")

print("\n" + "=" * 80)
print("CHECK FOR CATEGORY FIELDS IN INVOICES")
print("=" * 80)
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'invoices' 
    AND column_name LIKE '%category%'
""")
category_cols = cur.fetchall()
if category_cols:
    print("Category columns found:", [c[0] for c in category_cols])
else:
    print("No category columns found")

print("\n" + "=" * 80)
print("CHECK FOR GL CODE/ACCOUNT FIELDS IN INVOICES")
print("=" * 80)
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'invoices' 
    AND (column_name LIKE '%gl%' OR column_name LIKE '%account%')
""")
gl_cols = cur.fetchall()
if gl_cols:
    print("GL/Account columns found:", [c[0] for c in gl_cols])
else:
    print("No GL/Account columns found")

cur.close()
conn.close()
