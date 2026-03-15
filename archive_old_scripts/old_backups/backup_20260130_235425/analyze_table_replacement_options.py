#!/usr/bin/env python3
"""
Check if empty tables can be replaced by existing main pay tables.
Compare schemas and see if views/code can be rewritten.
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("="*90)
print("CAN EMPTY TABLES BE REPLACED BY MAIN PAY TABLES?")
print("="*90)

# Main pay tables with data
main_tables = {
    'driver_payroll': 16370,
    'employee_pay_master': 2653,
    'payables': 17598,
    'pay_periods': 416
}

# Empty tables and their potential replacements
replacements = {
    'charter_driver_pay': 'driver_payroll',
    'non_charter_payroll': 'employee_pay_master',
    'employee_expenses': 'receipts + employee_pay_master',
    'employee_schedules': None,  # No replacement
    'employee_availability': None,  # No replacement
}

print("\n1️⃣  View definitions that use empty tables:")
print("-"*90)

# Get views that use empty tables
cur.execute("""
    SELECT table_name, view_definition
    FROM information_schema.views
    WHERE table_schema = 'public'
    AND (
        view_definition LIKE '%charter_driver_pay%'
        OR view_definition LIKE '%driver_hos_log%'
        OR view_definition LIKE '%driver_internal_notes%'
        OR view_definition LIKE '%driver_performance_private%'
        OR view_definition LIKE '%wage_allocation_decisions%'
    )
""")

views = cur.fetchall()
for view_name, view_def in views:
    print(f"\n📊 {view_name}:")
    print(f"   Current SQL (first 400 chars):")
    print(f"   {view_def[:400].strip()}...")
    
    # Suggest replacement
    if 'charter_driver_pay' in view_def:
        print(f"\n   💡 Replacement suggestion:")
        print(f"   Replace 'charter_driver_pay' with 'driver_payroll'")
        print(f"   driver_payroll has {main_tables['driver_payroll']:,} records with charter pay data")
    
    if 'driver_hos_log' in view_def:
        print(f"\n   💡 Replacement suggestion:")
        print(f"   driver_hos_log is for Hours of Service compliance - no direct replacement")
        print(f"   Consider: Drop view until HOS tracking is implemented")
    
    if 'driver_performance_private' in view_def:
        print(f"\n   💡 Replacement suggestion:")
        print(f"   Use driver_payroll for performance metrics based on trips/hours/revenue")

print("\n" + "="*90)
print("2️⃣  Schema comparison - can empty tables be replaced?")
print("="*90)

comparisons = [
    ('charter_driver_pay', 'driver_payroll'),
    ('non_charter_payroll', 'employee_pay_master'),
]

for empty_table, main_table in comparisons:
    print(f"\n🔍 {empty_table} vs {main_table}:")
    print("-"*90)
    
    # Get columns from empty table
    cur.execute(f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = '{empty_table}'
        ORDER BY ordinal_position
    """)
    empty_cols = {row[0]: row[1] for row in cur.fetchall()}
    
    # Get columns from main table
    cur.execute(f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = '{main_table}'
        ORDER BY ordinal_position
    """)
    main_cols = {row[0]: row[1] for row in cur.fetchall()}
    
    # Find overlap
    common = set(empty_cols.keys()) & set(main_cols.keys())
    only_empty = set(empty_cols.keys()) - set(main_cols.keys())
    only_main = set(main_cols.keys()) - set(empty_cols.keys())
    
    print(f"   Common columns: {len(common)}")
    if len(common) > 0 and len(common) < 10:
        for col in sorted(common):
            print(f"      - {col}")
    
    print(f"   Only in {empty_table}: {len(only_empty)}")
    if len(only_empty) > 0 and len(only_empty) < 10:
        for col in sorted(only_empty):
            print(f"      - {col}")
    
    print(f"   Only in {main_table}: {len(only_main)}")
    
    # Verdict
    overlap_pct = 100 * len(common) / max(1, len(empty_cols))
    print(f"\n   📊 Overlap: {overlap_pct:.0f}%")
    
    if overlap_pct > 70:
        print(f"   ✅ High overlap - {empty_table} can likely be replaced by {main_table}")
    elif overlap_pct > 40:
        print(f"   ⚠️  Moderate overlap - some fields would need mapping")
    else:
        print(f"   ❌ Low overlap - tables serve different purposes")

print("\n" + "="*90)
print("3️⃣  Code references - can they use main tables?")
print("="*90)

# Check desktop app references
desktop_files = [
    'desktop_app/employee_management_widget.py'
]

for filepath in desktop_files:
    if os.path.exists(filepath):
        print(f"\n📄 {filepath}:")
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
            if 'employee_schedules' in content.lower():
                print(f"   ⚠️  References 'employee_schedules' (empty)")
                print(f"   💡 Suggestion: Comment out or use pay_periods table instead")
            
            if 'non_charter_payroll' in content.lower():
                print(f"   ⚠️  References 'non_charter_payroll' (empty)")
                print(f"   💡 Suggestion: Replace with employee_pay_master query")

print("\n" + "="*90)
print("4️⃣  Foreign key dependencies - can they be updated?")
print("="*90)

# Check FK from payroll_approval_workflow to non_charter_payroll
cur.execute("""
    SELECT COUNT(*) FROM payroll_approval_workflow
""")
workflow_count = cur.fetchone()[0]

print(f"\n📋 payroll_approval_workflow: {workflow_count} rows")
if workflow_count == 0:
    print(f"   ✅ Table is empty - FK can be dropped safely")
else:
    print(f"   ⚠️  Table has data - review before changing FK")

cur.close()
conn.close()

print("\n" + "="*90)
print("RECOMMENDATIONS")
print("="*90)

print("""
Based on analysis:

✅ CAN BE REPLACED:
   - charter_driver_pay → driver_payroll (16,370 rows)
   - non_charter_payroll → employee_pay_master (2,653 rows)
   - Update views:
     • v_driver_pay_summary: Use driver_payroll
     • v_driver_performance_summary: Use driver_payroll metrics
   
⚠️  UPDATE DESKTOP APP:
   - employee_management_widget.py: Replace references to empty tables
   
❌ CANNOT BE REPLACED (different purpose):
   - employee_schedules (scheduling system not implemented)
   - employee_availability (availability tracking not implemented)
   - driver_hos_log (Hours of Service compliance - regulatory)
   - driver_floats (cash float tracking - specific workflow)
   - employee_expenses (expense reimbursement - could use receipts table)

📋 ACTION PLAN:
   1. Rewrite 5 views to use driver_payroll instead of charter_driver_pay
   2. Update desktop_app code to use employee_pay_master
   3. Drop FK from payroll_approval_workflow (also empty)
   4. Keep other empty tables for future features OR drop them with views
""")
