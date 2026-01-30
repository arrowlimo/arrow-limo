#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check PostgreSQL database status for evidence of restores or data loss."""

import psycopg2
from datetime import datetime

print("=" * 120)
print("POSTGRESQL DATABASE STATUS CHECK")
print("=" * 120)
print()

# Connect to postgres database to check almsdata status
conn = psycopg2.connect(
    host='localhost',
    dbname='postgres',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("1. DATABASE INFORMATION:")
print("-" * 120)
cur.execute("""
    SELECT 
        datname,
        pg_size_pretty(pg_database_size(datname)) as size,
        (SELECT stats_reset FROM pg_stat_database WHERE datname = d.datname) as stats_reset
    FROM pg_database d
    WHERE datname = 'almsdata'
""")
db_info = cur.fetchone()
print(f"   Database: {db_info[0]}")
print(f"   Size: {db_info[1]}")
print(f"   Stats Reset: {db_info[2]}")
print()

cur.close()
conn.close()

# Connect to almsdata for more checks
conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("2. POSTGRESQL SERVER STATUS:")
print("-" * 120)
cur.execute("SELECT pg_postmaster_start_time(), pg_conf_load_time()")
times = cur.fetchone()
print(f"   PostgreSQL Started: {times[0]}")
print(f"   Config Last Loaded: {times[1]}")
print()

print("3. WRITE-AHEAD LOG (WAL) STATUS:")
print("-" * 120)
cur.execute("SELECT pg_current_wal_lsn(), pg_walfile_name(pg_current_wal_lsn())")
wal = cur.fetchone()
print(f"   Current WAL LSN: {wal[0]}")
print(f"   Current WAL File: {wal[1]}")
print()

print("4. DATABASE CONFLICTS (Restore/Rollback Indicators):")
print("-" * 120)
cur.execute("""
    SELECT 
        confl_tablespace,
        confl_lock,
        confl_snapshot,
        confl_bufferpin,
        confl_deadlock
    FROM pg_stat_database_conflicts
    WHERE datname = 'almsdata'
""")
conflicts = cur.fetchone()
if conflicts:
    print(f"   Tablespace Conflicts: {conflicts[0]}")
    print(f"   Lock Conflicts: {conflicts[1]}")
    print(f"   Snapshot Conflicts: {conflicts[2]}")
    print(f"   Buffer Pin Conflicts: {conflicts[3]}")
    print(f"   Deadlock Conflicts: {conflicts[4]}")
    
    if sum(conflicts) > 0:
        print(f"\n   ⚠️  TOTAL CONFLICTS: {sum(conflicts)} - May indicate restore/rollback activity")
else:
    print("   No conflict data available")
print()

print("5. RECENT ACTIVITY ON KEY TABLES:")
print("-" * 120)
# Check last vacuum/analyze times which can indicate recent table changes
cur.execute("""
    SELECT 
        schemaname,
        relname,
        last_vacuum,
        last_autovacuum,
        last_analyze,
        last_autoanalyze,
        n_tup_ins as inserts,
        n_tup_upd as updates,
        n_tup_del as deletes
    FROM pg_stat_user_tables
    WHERE relname IN ('receipts', 'banking_transactions', 'journal', 'payments', 'charters')
    ORDER BY relname
""")
table_stats = cur.fetchall()
for row in table_stats:
    print(f"\n   Table: {row[1]}")
    print(f"   Last Vacuum: {row[2]}")
    print(f"   Last Autovacuum: {row[3]}")
    print(f"   Last Analyze: {row[4]}")
    print(f"   Last Autoanalyze: {row[5]}")
    print(f"   Operations: {row[6]} inserts, {row[7]} updates, {row[8]} deletes")
print()

print("6. RECENT BACKUP/RESTORE TABLES:")
print("-" * 120)
cur.execute("""
    SELECT 
        table_name,
        (SELECT pg_size_pretty(pg_total_relation_size(quote_ident(table_name)))) as size
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name LIKE '%backup%'
    AND table_name LIKE '%2025%'
    ORDER BY table_name DESC
    LIMIT 10
""")
backups = cur.fetchall()
if backups:
    for backup in backups:
        print(f"   {backup[0]}: {backup[1]}")
else:
    print("   No recent backup tables found")
print()

print("=" * 120)
print("ANALYSIS")
print("=" * 120)
print()

# Check if PostgreSQL was restarted today
pg_start = times[0]
if pg_start.date() == datetime.now().date():
    print(f"⚠️  PostgreSQL was RESTARTED TODAY at {pg_start}")
    print("   This could indicate a restore operation or crash recovery")
else:
    print(f"✓ PostgreSQL has been running since {pg_start} (no restart today)")
print()

# Check stats reset
if db_info[2] and db_info[2].date() >= datetime.now().date():
    print(f"⚠️  Database stats were RESET TODAY at {db_info[2]}")
    print("   This often happens after a restore operation")
else:
    print(f"✓ Database stats have not been reset recently")
print()

cur.close()
conn.close()
