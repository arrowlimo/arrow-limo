#!/usr/bin/env python3
"""
Check if the 19 empty tables are used by other systems/code.
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

empty_tables = [
    'charter_driver_pay',
    'driver_app_actions',
    'driver_app_sessions',
    'driver_comms_log',
    'driver_disciplinary_actions',
    'driver_floats',
    'driver_hos_log',
    'driver_internal_notes',
    'driver_location_history',
    'driver_performance_private',
    'employee_availability',
    'employee_expenses',
    'employee_schedules',
    'employee_time_off_requests',
    'non_charter_payroll',
    'paul_pay_tracking',
    'payroll_approval_workflow',
    't4_compliance_corrections',
    'wage_allocation_decisions'
]

print("="*90)
print("CHECK IF EMPTY TABLES ARE USED BY OTHER SYSTEMS")
print("="*90)

# Check 1: Foreign key references TO these tables
print("\n1️⃣  Foreign key references TO these tables (other tables depend on them):")
print("-"*90)

has_references = False
for table in empty_tables:
    cur.execute(f"""
        SELECT
            tc.table_name AS referencing_table,
            kcu.column_name AS referencing_column
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE ccu.table_name = '{table}'
        AND tc.constraint_type = 'FOREIGN KEY'
    """)
    
    refs = cur.fetchall()
    if refs:
        has_references = True
        print(f"   ⚠️  {table}:")
        for ref_table, ref_col in refs:
            print(f"      ← {ref_table}.{ref_col}")

if not has_references:
    print("   ✅ None - no other tables reference these")

# Check 2: Foreign key references FROM these tables
print("\n2️⃣  Foreign key references FROM these tables (they reference other tables):")
print("-"*90)

has_fk = False
for table in empty_tables:
    cur.execute(f"""
        SELECT
            kcu.column_name,
            ccu.table_name AS foreign_table,
            ccu.column_name AS foreign_column
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.table_name = '{table}'
        AND tc.constraint_type = 'FOREIGN KEY'
    """)
    
    fks = cur.fetchall()
    if fks:
        has_fk = True
        print(f"   ℹ️  {table}:")
        for col, ftable, fcol in fks:
            print(f"      → {ftable}.{fcol} (via {col})")

if not has_fk:
    print("   ✅ None - safe to drop")

# Check 3: Used in views
print("\n3️⃣  Used in database views:")
print("-"*90)

cur.execute("""
    SELECT table_name, view_definition
    FROM information_schema.views
    WHERE table_schema = 'public'
""")

views = cur.fetchall()
used_in_views = {}

for view_name, view_def in views:
    for table in empty_tables:
        if table in view_def.lower():
            if table not in used_in_views:
                used_in_views[table] = []
            used_in_views[table].append(view_name)

if used_in_views:
    for table, view_list in used_in_views.items():
        print(f"   ⚠️  {table}: used in {len(view_list)} view(s)")
        for view in view_list:
            print(f"      - {view}")
else:
    print("   ✅ None - not used in any views")

cur.close()
conn.close()

# Check 4: Mentioned in codebase
print("\n4️⃣  Scanning codebase for references...")
print("-"*90)

code_dirs = ['scripts', 'modern_backend', 'desktop_app']
code_refs = {}

for table in empty_tables:
    refs = []
    for code_dir in code_dirs:
        if os.path.exists(code_dir):
            for root, dirs, files in os.walk(code_dir):
                for file in files:
                    if file.endswith(('.py', '.sql')):
                        filepath = os.path.join(root, file)
                        try:
                            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read().lower()
                                if table in content:
                                    refs.append(filepath)
                        except:
                            pass
    
    if refs:
        code_refs[table] = refs

if code_refs:
    print(f"   ⚠️  Found {len(code_refs)} tables referenced in code:")
    for table, files in sorted(code_refs.items()):
        print(f"\n   {table}:")
        for filepath in files[:3]:  # Show first 3 files
            print(f"      - {filepath}")
        if len(files) > 3:
            print(f"      ... and {len(files)-3} more")
else:
    print("   ✅ None - not referenced in Python/SQL code")

# Summary
print("\n" + "="*90)
print("SUMMARY - SAFE TO DROP?")
print("="*90)

safe_to_drop = []
needs_review = []

for table in empty_tables:
    issues = []
    
    # Re-check FK references
    cur = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD).cursor()
    cur.execute(f"""
        SELECT COUNT(*) FROM information_schema.table_constraints tc
        JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
        WHERE ccu.table_name = '{table}' AND tc.constraint_type = 'FOREIGN KEY'
    """)
    if cur.fetchone()[0] > 0:
        issues.append("FK references")
    
    if table in used_in_views:
        issues.append(f"{len(used_in_views[table])} views")
    
    if table in code_refs:
        issues.append(f"{len(code_refs[table])} code files")
    
    cur.close()
    
    if issues:
        needs_review.append((table, issues))
    else:
        safe_to_drop.append(table)

print(f"\n✅ Safe to drop ({len(safe_to_drop)} tables):")
for table in safe_to_drop:
    print(f"   - {table}")

if needs_review:
    print(f"\n⚠️  Needs review ({len(needs_review)} tables):")
    for table, issues in needs_review:
        print(f"   - {table}: {', '.join(issues)}")

print(f"\n📊 Total: {len(safe_to_drop)} safe, {len(needs_review)} need review")
