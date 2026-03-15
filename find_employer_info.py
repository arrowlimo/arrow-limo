#!/usr/bin/env python3
"""
Search for employer/company information in database
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="ArrowLimousine"
)

cur = conn.cursor()

# Check for company/settings tables
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND (table_name LIKE '%company%' 
         OR table_name LIKE '%employer%' 
         OR table_name LIKE '%business%'
         OR table_name LIKE '%setting%'
         OR table_name LIKE '%config%')
    ORDER BY table_name
""")

tables = cur.fetchall()
print("Company/Settings-related tables:")
for t in tables:
    print(f"  {t[0]}")
print()

# Check T2 corporate returns table (might have business number)
cur.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 't2_corporate_returns'
    )
""")

if cur.fetchone()[0]:
    print("Checking t2_corporate_returns table...")
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 't2_corporate_returns'
        AND column_name IN ('business_number', 'corporation_name', 'corporate_name', 'legal_name')
    """)
    cols = cur.fetchall()
    for col in cols:
        print(f"  Column: {col[0]} ({col[1]})")
    
    # Try to get business number from T2 returns
    cur.execute("""
        SELECT business_number, tax_year 
        FROM t2_corporate_returns 
        WHERE business_number IS NOT NULL 
        LIMIT 5
    """)
    rows = cur.fetchall()
    if rows:
        print("\n  Sample business numbers:")
        for row in rows:
            print(f"    {row[0]} (Tax Year: {row[1]})")
    print()

# Check for environment/config
try:
    cur.execute("""
        SELECT * FROM settings LIMIT 1
    """)
    print("Settings table exists")
except:
    print("No settings table found")

cur.close()
conn.close()
