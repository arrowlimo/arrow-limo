#!/usr/bin/env python3
"""
Delete all backup and staging tables.
Safe cleanup after migration work is complete.
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")


def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    # Find all backup/staging/archived tables
    cur.execute("""
        SELECT tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
        FROM pg_tables 
        WHERE schemaname = 'public' 
          AND (tablename LIKE '%backup%' 
            OR tablename LIKE '%staging%'
            OR tablename LIKE '%archived%'
            OR tablename LIKE '%_20%'
            OR tablename LIKE 'lms2026_%')
        ORDER BY tablename
    """)
    
    tables = cur.fetchall()
    
    if not tables:
        print("✓ No backup/staging tables found")
        conn.close()
        return
    
    print("="*80)
    print(f"DELETING {len(tables)} BACKUP/STAGING TABLES")
    print("="*80)
    
    total_size = 0
    deleted_count = 0
    
    for table_name, size in tables:
        print(f"Dropping {table_name:60} {size}")
        try:
            cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
            deleted_count += 1
        except Exception as e:
            print(f"  ⚠️  Error dropping {table_name}: {e}")
    
    conn.commit()
    
    print("="*80)
    print(f"✓ Deleted {deleted_count} tables successfully")
    print("="*80)
    
    # Verify cleanup
    cur.execute("""
        SELECT COUNT(*) 
        FROM pg_tables 
        WHERE schemaname = 'public' 
          AND (tablename LIKE '%backup%' 
            OR tablename LIKE '%staging%'
            OR tablename LIKE '%archived%'
            OR tablename LIKE '%_20%'
            OR tablename LIKE 'lms2026_%')
    """)
    
    remaining = cur.fetchone()[0]
    if remaining == 0:
        print("✓ All backup/staging tables removed")
    else:
        print(f"⚠️  {remaining} tables still remain")
    
    conn.close()


if __name__ == '__main__':
    main()
