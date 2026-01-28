#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Check for evidence of Fibrenew reconciliation work that may have been lost.
"""

import psycopg2
from datetime import datetime, timedelta

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 120)
print("FIBRENEW RECONCILIATION STATUS CHECK")
print("=" * 120)
print()

# Check for Fibrenew-specific tables
print("1. FIBRENEW-SPECIFIC TABLES:")
print("-" * 120)
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name ILIKE '%fibrenew%'
    ORDER BY table_name
""")
fibrenew_tables = cur.fetchall()
if fibrenew_tables:
    for table in fibrenew_tables:
        print(f"   ✓ {table[0]}")
else:
    print("   ✗ No Fibrenew-specific tables found")
print()

# Check receipts with Fibrenew
print("2. FIBRENEW RECEIPTS:")
print("-" * 120)
cur.execute("""
    SELECT 
        COUNT(*) as count,
        MIN(receipt_date) as first_date,
        MAX(receipt_date) as last_date,
        SUM(gross_amount) as total_amount,
        MAX(created_at) as last_created
    FROM receipts
    WHERE vendor_name ILIKE '%fibrenew%'
""")
receipts_data = cur.fetchone()
if receipts_data[0] > 0:
    print(f"   ✓ Found {receipts_data[0]} Fibrenew receipts")
    print(f"   Date Range: {receipts_data[1]} to {receipts_data[2]}")
    print(f"   Total Amount: ${receipts_data[3]:,.2f}")
    print(f"   Last Created: {receipts_data[4]}")
else:
    print("   ✗ No Fibrenew receipts found")
print()

# Check for recent Fibrenew-related work (last 7 days)
print("3. RECENT FIBRENEW ACTIVITY (Last 7 Days):")
print("-" * 120)
seven_days_ago = datetime.now() - timedelta(days=7)

cur.execute("""
    SELECT 
        COUNT(*) as count,
        MAX(created_at) as last_created
    FROM receipts
    WHERE vendor_name ILIKE '%%fibrenew%%'
    AND created_at >= %s
""", (seven_days_ago,))
recent = cur.fetchone()
if recent and recent[0] and recent[0] > 0:
    print(f"   ⚠️  Found {recent[0]} Fibrenew receipts created in last 7 days")
    print(f"   Last Created: {recent[1]}")
else:
    print("   ✗ No recent Fibrenew activity in receipts")
print()

# Check for Fibrenew ledger or balance tracking
print("4. FIBRENEW LEDGER/BALANCE TABLES:")
print("-" * 120)
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND (table_name ILIKE '%ledger%' OR table_name ILIKE '%balance%')
    AND table_name ILIKE '%fibrenew%'
    ORDER BY table_name
""")
ledger_tables = cur.fetchall()
if ledger_tables:
    for table in ledger_tables:
        print(f"   ✓ {table[0]}")
        # Check row count
        cur.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cur.fetchone()[0]
        print(f"      Rows: {count}")
else:
    print("   ✗ No Fibrenew ledger tables found")
print()

# Check backup tables that might contain lost Fibrenew work
print("5. FIBRENEW-RELATED BACKUP TABLES:")
print("-" * 120)
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name ILIKE '%backup%'
    AND table_name ILIKE '%fibrenew%'
    ORDER BY table_name
""")
backup_tables = cur.fetchall()
if backup_tables:
    for table in backup_tables:
        print(f"   ✓ {table[0]}")
        # Get row count and date range
        cur.execute(f"""
            SELECT COUNT(*), 
                   MIN(receipt_date) as first_date,
                   MAX(receipt_date) as last_date
            FROM {table[0]}
        """)
        backup_data = cur.fetchone()
        print(f"      Rows: {backup_data[0]}, Date Range: {backup_data[1]} to {backup_data[2]}")
else:
    print("   ✗ No Fibrenew backup tables found")
print()

# Check journal entries mentioning Fibrenew
print("6. JOURNAL ENTRIES (Fibrenew):")
print("-" * 120)
cur.execute("""
    SELECT COUNT(*), SUM("Debit"), SUM("Credit")
    FROM journal
    WHERE "Name" ILIKE '%%fibrenew%%' OR "Memo/Description" ILIKE '%%fibrenew%%'
""")
journal_data = cur.fetchone()
if journal_data and journal_data[0] and journal_data[0] > 0:
    print(f"   ✓ Found {journal_data[0]} journal entries")
    debit = journal_data[1] if journal_data[1] else 0
    credit = journal_data[2] if journal_data[2] else 0
    print(f"   Total Debits: ${debit:,.2f}")
    print(f"   Total Credits: ${credit:,.2f}")
else:
    print("   ✗ No Fibrenew journal entries found")
print()

# Check for any tables modified today (Dec 8, 2025)
print("7. TABLES MODIFIED TODAY (Dec 8, 2025):")
print("-" * 120)
cur.execute("""
    SELECT 
        schemaname,
        tablename,
        last_vacuum,
        last_autovacuum,
        last_analyze,
        last_autoanalyze
    FROM pg_stat_user_tables
    WHERE (last_analyze > CURRENT_DATE OR last_autoanalyze > CURRENT_DATE)
    AND (tablename ILIKE '%fibrenew%' OR tablename ILIKE '%receipt%' OR tablename ILIKE '%vendor%')
    ORDER BY GREATEST(
        COALESCE(last_vacuum, '1970-01-01'::timestamp),
        COALESCE(last_autovacuum, '1970-01-01'::timestamp),
        COALESCE(last_analyze, '1970-01-01'::timestamp),
        COALESCE(last_autoanalyze, '1970-01-01'::timestamp)
    ) DESC
""")
today_activity = cur.fetchall()
if today_activity:
    print("   ⚠️  Tables with activity today:")
    for row in today_activity:
        print(f"   {row[1]}: last_analyze={row[4]}, last_autoanalyze={row[5]}")
else:
    print("   ✗ No table activity detected today")
print()

print("=" * 120)
print("SUMMARY")
print("=" * 120)
print()
print("If Fibrenew reconciliation work was completed today and is now missing,")
print("possible causes:")
print("  1. SSD/drive rollback or filesystem corruption")
print("  2. Database restore from old backup")
print("  3. Transaction rollback/uncommitted work")
print("  4. Work done in different database/schema")
print("  5. PostgreSQL WAL (Write-Ahead Log) issue")
print()

cur.close()
conn.close()
