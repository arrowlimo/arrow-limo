"""
BACKUP TABLE CLEANUP GUIDE
Identify which backup tables are safe to delete
"""
import os
import psycopg2
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 100)
print("BACKUP TABLE CLEANUP GUIDE - What's Safe to Delete?")
print("=" * 100)

# Find all backup/archive tables with sizes
cur.execute("""
SELECT 
  t.tablename as table_name,
  CASE 
    WHEN t.tablename LIKE '%_archive%' THEN 'ARCHIVE'
    WHEN t.tablename LIKE '%_backup_%' THEN 'BACKUP'
    WHEN t.tablename LIKE '%_old%' THEN 'OLD'
    WHEN t.tablename LIKE '%qb_%' THEN 'QB_LEGACY'
    WHEN t.tablename LIKE 'square_%' THEN 'SQUARE_LEGACY'
    ELSE 'UNKNOWN'
  END as category,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
  pg_total_relation_size(schemaname||'.'||tablename) as size_bytes,
  (SELECT COUNT(*) FROM information_schema.tables 
   WHERE table_schema='public' AND table_name=t.tablename) as table_exists
FROM pg_tables t
WHERE t.schemaname = 'public'
  AND (t.tablename LIKE '%_backup%' OR t.tablename LIKE '%_archive%' OR t.tablename LIKE '%_old%')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
""")

backups = cur.fetchall()

# Categorize backups
by_category = defaultdict(list)
for table_name, category, size_str, size_bytes, exists in backups:
    by_category[category].append((table_name, size_str, size_bytes))

print("\n" + "=" * 100)
print("BACKUP TABLES BY CATEGORY")
print("=" * 100)

total_size = 0
for category in ['ARCHIVE', 'BACKUP', 'OLD', 'QB_LEGACY', 'SQUARE_LEGACY', 'UNKNOWN']:
    if category in by_category:
        tables = by_category[category]
        category_size = sum(size_bytes for _, _, size_bytes in tables)
        total_size += category_size
        
        print(f"\n[{category}] - Total: {len(tables)} tables, {sum(t[2] for t in tables) / (1024**3):.2f} GB")
        print("-" * 100)
        
        for table_name, size_str, size_bytes in tables[:10]:
            print(f"  {table_name:<55} {size_str:>12}")
        
        if len(tables) > 10:
            remaining_count = len(tables) - 10
            remaining_size = sum(t[2] for t in tables[10:]) / (1024**2)
            print(f"  ... and {remaining_count} more tables ({remaining_size:.1f} MB)")

print(f"\n{'='*100}")
print(f"TOTAL BACKUP SIZE: {total_size / (1024**3):.2f} GB across {len(backups)} backup tables")
print(f"{'='*100}")

# Detailed breakdown
print("\n" + "=" * 100)
print("SAFE TO DELETE (TIER 1) - Automatic/Test Snapshots")
print("=" * 100)
print("""
These are automatic snapshots from testing/debugging. Safe because:
✅ Data is in the main table already
✅ These are duplicates of current data
✅ No business logic depends on them
✅ Recent backups exist elsewhere

Pattern: *_backup_YYYYMMDD_* or *_backup_2012-2017
""")

cur.execute("""
SELECT 
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
  CASE 
    WHEN tablename LIKE '%banking_transactions_%_backup_%' THEN 'Banking snapshots'
    WHEN tablename LIKE '%payments_%_backup_%' THEN 'Payment snapshots'
    WHEN tablename LIKE '%receipts_%_backup_%' THEN 'Receipt snapshots'
    WHEN tablename LIKE '%charters_%_backup_%' THEN 'Charter snapshots'
    WHEN tablename LIKE '%_backup_2012%' THEN 'Year 2012 archives'
    WHEN tablename LIKE '%_backup_2013%' THEN 'Year 2013 archives'
    WHEN tablename LIKE '%_backup_2014%' THEN 'Year 2014 archives'
    WHEN tablename LIKE '%_backup_2015%' THEN 'Year 2015 archives'
    WHEN tablename LIKE '%_backup_2016%' THEN 'Year 2016 archives'
    WHEN tablename LIKE '%_backup_2017%' THEN 'Year 2017 archives'
    ELSE 'Other dated backups'
  END as reason
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename LIKE '%_backup_%'
  AND tablename ~ '_backup_20[01][0-9]'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 30
""")

tier1 = cur.fetchall()
print(f"\nFound {len(tier1)} tables matching TIER 1 criteria:\n")
for table, size, reason in tier1:
    print(f"  DROP TABLE {table};  -- {size:>10} ({reason})")

# Calculate recovery
cur.execute("""
SELECT ROUND(SUM(pg_total_relation_size(schemaname||'.'||tablename)) / (1024.0^3), 2) as total_gb
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename LIKE '%_backup_%'
  AND tablename ~ '_backup_20[01][0-9]'
""")
tier1_recovery = cur.fetchone()[0] or 0
print(f"\n💾 Recovery if deleted: {tier1_recovery:.2f} GB")

# Backup summary
print("\n" + "=" * 100)
print("RECENT BACKUPS (LAST 30 DAYS) - KEEP THESE")
print("=" * 100)

cur.execute("""
SELECT 
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename LIKE '%_backup_%'
  AND tablename ~ '_backup_202501'  -- January 2025
ORDER BY tablename DESC
LIMIT 20
""")

recent = cur.fetchall()
print(f"\nRecent backups (keep for reference): {len(recent)} tables\n")
for table, size in recent:
    print(f"  {table:<55} {size:>10}")

# Banking specific backups
print("\n" + "=" * 100)
print("BANKING TRANSACTION BACKUPS - Legacy Archives")
print("=" * 100)

cur.execute("""
SELECT 
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
  CASE 
    WHEN tablename LIKE '%_backup_2012%' THEN '2012'
    WHEN tablename LIKE '%_backup_2013%' THEN '2013'
    WHEN tablename LIKE '%_backup_2014%' THEN '2014'
    WHEN tablename LIKE '%_backup_2015%' THEN '2015'
    WHEN tablename LIKE '%_backup_2016%' THEN '2016'
    WHEN tablename LIKE '%_backup_2017%' THEN '2017'
    ELSE 'OTHER'
  END as year
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename LIKE 'banking_transactions_%_backup%'
ORDER BY tablename
""")

banking_backups = cur.fetchall()
print(f"\nFound {len(banking_backups)} banking_transactions backup tables\n")

# Group by year
by_year = defaultdict(list)
for table, size, year in banking_backups:
    by_year[year].append((table, size))

for year in sorted(by_year.keys()):
    tables = by_year[year]
    print(f"  Year {year}: {len(tables)} tables")
    for table, size in tables[:3]:
        print(f"    - {table:<50} {size:>10}")
    if len(tables) > 3:
        print(f"    ... and {len(tables)-3} more")

# Recommendations
print("\n" + "=" * 100)
print("RECOMMENDED CLEANUP STRATEGY")
print("=" * 100)

print("""
IMMEDIATE (Safe - DO NOW):
  1. Delete all TIER 1 backups (snapshot tables from 2012-2017)
     Recovery: ~1-2 GB
     Risk: NONE - these are automatic duplicates

     Example:
       DROP TABLE IF EXISTS banking_transactions_1615_backup_2012;
       DROP TABLE IF EXISTS banking_transactions_1615_backup_2013;
       ... (repeat for all year-based backups)

WEEK 1 (Verify first):
  2. Archive banking_transactions_1615_backup_201X tables
     Reason: Historical but not needed in live DB
     Recovery: 300-500 MB
     Risk: LOW (but create backup first, archive to external storage)

  3. Delete Tier 1 _archive tables
     Recovery: 100-200 MB
     Risk: NONE if they're duplicates of current tables

ONGOING:
  4. Stop creating new backup tables during routine tasks
     Use single versioned backup instead: `payments_backup_LATEST`
     Clean up old versions after 30 days
""")

# Generate DELETE script
print("\n" + "=" * 100)
print("GENERATED SQL: Delete TIER 1 Backups")
print("=" * 100)
print("""
-- Create this as a file, review, then execute
BEGIN;

-- Step 1: Count backups to be deleted
SELECT COUNT(*) as tables_to_delete
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename LIKE '%_backup_%'
  AND tablename ~ '_backup_20[01][0-9]';

-- Step 2: Calculate space to be freed
SELECT ROUND(SUM(pg_total_relation_size(schemaname||'.'||tablename)) / (1024.0^3), 2) as gb_to_recover
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename LIKE '%_backup_%'
  AND tablename ~ '_backup_20[01][0-9]';

-- Step 3: Delete (comment out until ready)
-- DO LANGUAGE plpgsql $$
-- DECLARE
--   r RECORD;
-- BEGIN
--   FOR r IN 
--     SELECT tablename FROM pg_tables 
--     WHERE schemaname = 'public'
--       AND tablename LIKE '%_backup_%'
--       AND tablename ~ '_backup_20[01][0-9]'
--   LOOP
--     EXECUTE 'DROP TABLE ' || r.tablename;
--     RAISE NOTICE 'Dropped table: %', r.tablename;
--   END LOOP;
-- END $$;

-- COMMIT;  -- Uncomment when ready
""")

cur.close()
conn.close()

print(f"\n{'='*100}")
print("Next step: Review findings and decide cleanup strategy")
print("Questions to answer:")
print("  1. Do you need these backups for compliance/audit purposes?")
print("  2. Are there offsite backups (external storage, AWS)?")
print("  3. Should we proceed with deletion or archive to external first?")
print(f"{'='*100}")
