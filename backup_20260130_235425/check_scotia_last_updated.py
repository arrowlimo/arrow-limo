#!/usr/bin/env python
"""
Check when Scotia 6011 banking data was last accessed/updated.
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

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
print("SCOTIA 6011 DATA - LAST ACCESS/UPDATE TIMESTAMPS")
print("=" * 100)

# Check if created_at/updated_at columns exist
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'banking_transactions' 
    AND column_name IN ('created_at', 'updated_at')
    ORDER BY column_name
""")

timestamp_cols = cur.fetchall()
print(f"\nTimestamp columns available: {[col[0] for col in timestamp_cols]}")

if timestamp_cols:
    for col_name, data_type in timestamp_cols:
        cur.execute(f"""
            SELECT 
                EXTRACT(YEAR FROM transaction_date)::int as year,
                COUNT(*) as records,
                MIN({col_name}) as earliest_timestamp,
                MAX({col_name}) as latest_timestamp
            FROM banking_transactions
            WHERE account_number = '903990106011'
            AND {col_name} IS NOT NULL
            GROUP BY EXTRACT(YEAR FROM transaction_date)
            ORDER BY year
        """)
        
        print(f"\n{col_name.upper()} timestamps by year:")
        print("-" * 100)
        results = cur.fetchall()
        if results:
            for year, cnt, earliest, latest in results:
                print(f"  {year}: {cnt} records | Earliest: {earliest} | Latest: {latest}")
        else:
            print(f"  No {col_name} timestamps found")
    
    # Overall latest update
    cur.execute("""
        SELECT 
            MAX(created_at) as last_created,
            MAX(updated_at) as last_updated
        FROM banking_transactions
        WHERE account_number = '903990106011'
    """)
    
    last_created, last_updated = cur.fetchone()
    print("\n" + "=" * 100)
    print("MOST RECENT ACTIVITY:")
    print("-" * 100)
    if last_created:
        print(f"Last record created: {last_created}")
    if last_updated:
        print(f"Last record updated: {last_updated}")
else:
    print("\n⚠ No timestamp columns found in banking_transactions table")
    print("Cannot determine when data was last modified")

# Check table modification from pg_stat
cur.execute("""
    SELECT 
        schemaname,
        relname,
        n_tup_ins as inserts,
        n_tup_upd as updates,
        n_tup_del as deletes,
        last_vacuum,
        last_autovacuum,
        last_analyze,
        last_autoanalyze
    FROM pg_stat_user_tables
    WHERE relname = 'banking_transactions'
""")

result = cur.fetchone()
if result:
    print("\n" + "=" * 100)
    print("TABLE STATISTICS (pg_stat_user_tables):")
    print("-" * 100)
    schema, table, ins, upd, dels, vac, autovac, analyze, autoanalyze = result
    print(f"Total inserts: {ins:,}")
    print(f"Total updates: {upd:,}")
    print(f"Total deletes: {dels:,}")
    if vac:
        print(f"Last vacuum: {vac}")
    if autovac:
        print(f"Last autovacuum: {autovac}")
    if analyze:
        print(f"Last analyze: {analyze}")
    if autoanalyze:
        print(f"Last autoanalyze: {autoanalyze}")

print("\n" + "=" * 100)

cur.close()
conn.close()
