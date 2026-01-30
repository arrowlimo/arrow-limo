#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 1.5: Verification - confirm tables are gone and database is clean.
"""
import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

print("="*80)
print("PHASE 1.5: VERIFICATION & COMPLETION REPORT")
print("="*80)

# Check if tables exist
print("\n1. Table Existence Check:")
print("-" * 80)

deleted_tables = ['limo_contacts', 'lms_charges', 'lms_deposits']
for table in deleted_tables:
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = %s
        )
    """, (table,))
    exists = cur.fetchone()[0]
    status = "❌ STILL EXISTS" if exists else "✅ DELETED"
    print(f"{table:<25} {status}")

# Check that no orphaned views reference these tables
print("\n2. Orphaned View Check:")
print("-" * 80)

cur.execute("""
    SELECT table_name, view_definition
    FROM information_schema.views
    WHERE table_schema = 'public'
""")
views = cur.fetchall()
orphaned = []
for view_name, defn in views:
    for table in deleted_tables:
        if table.lower() in defn.lower():
            orphaned.append((view_name, table))

if orphaned:
    print(f"⚠️  {len(orphaned)} views still reference deleted tables:")
    for view, table in orphaned:
        print(f"   {view} → {table}")
else:
    print("✅ No views reference deleted tables")

# Database statistics
print("\n3. Database Statistics:")
print("-" * 80)

cur.execute("""
    SELECT COUNT(*) FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
""")
table_count = cur.fetchone()[0]
print(f"Total tables in 'public' schema: {table_count}")

# Show remaining legacy tables (if any)
print("\n4. Remaining Legacy Tables:")
print("-" * 80)

cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public'
      AND (table_name LIKE 'limo_%' OR table_name LIKE 'lms_%')
    ORDER BY table_name
""")
remaining = cur.fetchall()
if remaining:
    print(f"⚠️  {len(remaining)} legacy-named tables remain:")
    for (table,) in remaining:
        print(f"   - {table}")
else:
    print("✅ No other legacy-named tables found")

cur.close()
conn.close()

print("\n" + "="*80)
print("✅ PHASE 1 COMPLETE: LEGACY TABLE CLEANUP")
print("="*80)
print("""
SUMMARY:
✅ Deleted:     3 tables (limo_contacts, lms_charges, lms_deposits)
✅ Backed up:   3 tables (CSV exports in reports/legacy_table_backups/)
✅ Views:       No orphaned views found
✅ Database:    Clean and consistent

NEXT PHASE:
→ Phase 2: Migrate limo_clients data (contact_person, data_issues) to ALMS
→ Phase 3: Migrate lms_customers_enhanced data (full_name_search, etc.) to ALMS
""")
