#!/usr/bin/env python
"""
Check complete date coverage and data sources
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()

# Overall range
cur.execute("SELECT MIN(date), MAX(date), COUNT(*) FROM general_ledger")
min_date, max_date, total = cur.fetchone()
print("="*80)
print("GENERAL LEDGER COMPLETE STATUS")
print("="*80)
print(f"Date range: {min_date} to {max_date}")
print(f"Total records: {total:,}")

# Pre-2012 breakdown
print("\nPRE-2012 BREAKDOWN BY YEAR:")
print("-"*80)
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM date)::int as year,
        COUNT(*) as records,
        COUNT(DISTINCT source_file) as sources
    FROM general_ledger
    WHERE date < '2012-01-01'
    GROUP BY year
    ORDER BY year
""")

for year, count, sources in cur.fetchall():
    print(f"  {year}: {count:,} records from {sources} source(s)")

# By source file
print("\nBY SOURCE FILE:")
print("-"*80)
cur.execute("""
    SELECT 
        COALESCE(source_file, '[Original Import]') as source,
        COUNT(*) as records,
        MIN(date) as min_date,
        MAX(date) as max_date
    FROM general_ledger
    GROUP BY source_file
    ORDER BY source_file NULLS FIRST
""")

for source, count, min_d, max_d in cur.fetchall():
    print(f"  {source}:")
    print(f"    Records: {count:,}")
    print(f"    Range: {min_d} to {max_d}")

print("\n" + "="*80)

conn.close()
