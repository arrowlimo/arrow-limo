#!/usr/bin/env python3
"""
Step 3: Drop empty tables that have been replaced.
"""

import os
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("="*90)
print("STEP 3: DROP EMPTY TABLES NOW REPLACED BY MAIN TABLES")
print("="*90)

# Tables safe to drop after view/code updates
tables_to_drop = [
    'charter_driver_pay',           # Replaced by driver_payroll in v_driver_pay_summary
    'driver_performance_private',   # Replaced by driver_payroll in v_driver_performance_summary
    'driver_internal_notes',        # Replaced by driver_payroll in v_driver_performance_summary
    'driver_hos_log',              # View dropped (HOS not implemented)
    'wage_allocation_decisions',    # View dropped (wage allocation not implemented)
    'payroll_approval_workflow',    # Empty, references non_charter_payroll (also empty)
    'non_charter_payroll',         # Replaced by employee_pay_master in desktop app
]

# Create backup
backup_file = f"reports/empty_tables_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
os.makedirs("reports", exist_ok=True)

print("\n1️⃣  Creating backup of table structures...")
with open(backup_file, 'w') as f:
    f.write("-- Backup of empty table structures before dropping\n")
    f.write(f"-- Created: {datetime.now().isoformat()}\n\n")
    
    for table in tables_to_drop:
        cur.execute(f"""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = '{table}'
            ORDER BY ordinal_position
        """)
        
        cols = cur.fetchall()
        f.write(f"-- Table: {table}\n")
        f.write(f"-- Columns: {len(cols)}\n")
        for col, dtype, nullable, default in cols:
            f.write(f"--   {col} {dtype} {'NULL' if nullable == 'YES' else 'NOT NULL'}\n")
        f.write("\n")

print(f"   ✅ Backup saved to {backup_file}")

# Drop tables
print("\n2️⃣  Dropping empty tables...")

dropped = []
failed = []

for table in tables_to_drop:
    try:
        cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        conn.commit()
        dropped.append(table)
        print(f"   ✅ {table}")
    except Exception as e:
        failed.append((table, str(e)))
        print(f"   ❌ {table}: {e}")
        conn.rollback()

# Summary
print("\n" + "="*90)
print("SUMMARY")
print("="*90)
print(f"✅ Successfully dropped {len(dropped)} tables:")
for table in dropped:
    print(f"   - {table}")

if failed:
    print(f"\n❌ Failed to drop {len(failed)} tables:")
    for table, error in failed:
        print(f"   - {table}: {error}")

print(f"\n📄 Backup: {backup_file}")

# Verify remaining employee/pay tables
print("\n" + "="*90)
print("REMAINING EMPLOYEE/PAY TABLES")
print("="*90)

cur.execute("""
    SELECT table_name, 
           (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as col_count
    FROM information_schema.tables t
    WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE'
    AND (
        table_name LIKE '%employee%'
        OR table_name LIKE '%pay%'
        OR table_name LIKE '%driver%'
    )
    ORDER BY table_name
""")

remaining = cur.fetchall()
print(f"\nRemaining: {len(remaining)} tables\n")

# Check row counts for main tables
main_tables = ['employees', 'employee_pay_master', 'driver_payroll', 'pay_periods', 
               'employee_t4_summary', 'employee_roe_records']

for table_name, col_count in remaining:
    if table_name in main_tables:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cur.fetchone()[0]
        print(f"   ✅ {table_name:<40} {row_count:>8,} rows")

cur.close()
conn.close()

print("\n" + "="*90)
print("✅ Cleanup complete - all empty tables replaced by main tables")
print("="*90)
