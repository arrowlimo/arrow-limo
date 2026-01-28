#!/usr/bin/env python
"""
Check for Scotia 6011 updates specifically on December 8, 2025.
"""
import psycopg2
import os
from datetime import datetime, date

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

conn = get_db_connection()
cur = conn.cursor()

print("=" * 100)
print(f"SCOTIA 6011 DATA - ACTIVITY ON DECEMBER 8, 2025")
print("=" * 100)

# Check for records created today
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date)::int as year,
        COUNT(*) as count
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND DATE(created_at) = '2025-12-08'
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY year
""")

created_today = cur.fetchall()
if created_today:
    print("\nRecords CREATED on December 8, 2025:")
    for year, cnt in created_today:
        print(f"  {year}: {cnt} records")
    total_created = sum(cnt for _, cnt in created_today)
    print(f"  TOTAL: {total_created} records created today")
else:
    print("\n✗ No records created on December 8, 2025")

# Check for records updated today
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date)::int as year,
        COUNT(*) as count
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND DATE(updated_at) = '2025-12-08'
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY year
""")

updated_today = cur.fetchall()
if updated_today:
    print("\nRecords UPDATED on December 8, 2025:")
    for year, cnt in updated_today:
        print(f"  {year}: {cnt} records")
    total_updated = sum(cnt for _, cnt in updated_today)
    print(f"  TOTAL: {total_updated} records updated today")
else:
    print("\n✗ No records updated on December 8, 2025")

# Show most recent timestamps
cur.execute("""
    SELECT 
        MAX(created_at) as last_created,
        MAX(updated_at) as last_updated
    FROM banking_transactions
    WHERE account_number = '903990106011'
""")

last_created, last_updated = cur.fetchone()
print("\n" + "=" * 100)
print("MOST RECENT TIMESTAMPS:")
print(f"  Last created: {last_created}")
print(f"  Last updated: {last_updated}")

# Check database server time
cur.execute("SELECT CURRENT_TIMESTAMP")
db_time = cur.fetchone()[0]
print(f"  Database server time: {db_time}")
print(f"  Python script time: {datetime.now()}")

print("\n" + "=" * 100)

cur.close()
conn.close()
