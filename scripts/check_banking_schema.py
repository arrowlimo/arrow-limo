#!/usr/bin/env python3
"""Check banking_transactions schema"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check banking_transactions columns
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'banking_transactions'
    ORDER BY ordinal_position
""")

print("banking_transactions columns:")
for col, dtype in cur.fetchall():
    print(f"  {col}: {dtype}")
tables = cur.fetchall()

print("\nBANKING TABLES:")
for table, in tables:
    print(f"\n{table}:")
    cur.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name='{table}'
        ORDER BY ordinal_position
    """)
    cols = cur.fetchall()
    for col, dtype in cols:
        print(f"  {col}: {dtype}")
    
    # Get row count
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"  ROW COUNT: {count:,}")

conn.close()
