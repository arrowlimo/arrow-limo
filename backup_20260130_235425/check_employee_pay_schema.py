#!/usr/bin/env python3
"""
Check if employee pay tables are properly set up for data import.
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
print("EMPLOYEE PAY SCHEMA READINESS CHECK")
print("="*90)

# Check main employee pay tables
tables_to_check = [
    'employees',
    'employee_pay_master',
    'driver_payroll',
    'pay_periods',
    'employee_t4_summary',
    'employee_roe_records'
]

print("\n1️⃣  Table existence check:")
print("-"*90)
for table in tables_to_check:
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        )
    """, (table,))
    exists = cur.fetchone()[0]
    
    if exists:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"   ✅ {table:<30} (exists, {count:,} rows)")
    else:
        print(f"   ❌ {table:<30} (MISSING)")

# Check key columns in employee_pay_master
print("\n2️⃣  employee_pay_master schema:")
print("-"*90)
cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'employee_pay_master'
    ORDER BY ordinal_position
""")

for col, dtype, nullable, default in cur.fetchall():
    default_str = f" DEFAULT {default}" if default else ""
    nullable_str = "NULL" if nullable == 'YES' else "NOT NULL"
    print(f"   {col:<30} {dtype:<20} {nullable_str:<10} {default_str}")

# Check constraints
print("\n3️⃣  Constraints on employee_pay_master:")
print("-"*90)
cur.execute("""
    SELECT constraint_name, constraint_type
    FROM information_schema.table_constraints
    WHERE table_name = 'employee_pay_master'
""")

constraints = cur.fetchall()
if constraints:
    for name, ctype in constraints:
        print(f"   {ctype:<15} {name}")
else:
    print("   ⚠️  No constraints found")

# Check CHECK constraints specifically
cur.execute("""
    SELECT constraint_name, check_clause
    FROM information_schema.check_constraints
    WHERE constraint_name LIKE '%employee_pay%' OR constraint_name LIKE '%check_%'
    ORDER BY constraint_name
""")

check_constraints = cur.fetchall()
if check_constraints:
    print("\n4️⃣  CHECK constraints:")
    print("-"*90)
    for name, clause in check_constraints:
        if 'employee' in name.lower() or 'pay' in name.lower() or name in ['check_net', 'check_pay', 'check_hours']:
            print(f"   {name}: {clause[:80]}")

# Check foreign keys
print("\n5️⃣  Foreign key relationships:")
print("-"*90)
cur.execute("""
    SELECT
        tc.constraint_name,
        kcu.column_name,
        ccu.table_name AS foreign_table_name,
        ccu.column_name AS foreign_column_name
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
    JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
    WHERE tc.table_name = 'employee_pay_master'
    AND tc.constraint_type = 'FOREIGN KEY'
""")

fks = cur.fetchall()
if fks:
    for fk_name, col, ftable, fcol in fks:
        print(f"   {col} → {ftable}.{fcol}")
else:
    print("   ℹ️  No foreign keys defined")

print("\n" + "="*90)
print("READINESS SUMMARY")
print("="*90)

# Check if ready for import
issues = []

# Check if check_net constraint exists (might block imports with negative net_pay)
cur.execute("""
    SELECT EXISTS (
        SELECT 1 FROM information_schema.check_constraints
        WHERE constraint_name = 'check_net'
    )
""")
if not cur.fetchone()[0]:
    issues.append("⚠️  check_net constraint is MISSING (will allow negative net_pay)")

print(f"\n{'Status':<20} {'Details'}")
print("-"*90)
if not issues:
    print(f"{'✅ READY':<20} All tables exist, schema looks good")
else:
    for issue in issues:
        print(issue)

print("\n💡 To add employee pay data, ensure:")
print("   1. employee_id matches employees table")
print("   2. pay_period_id matches pay_periods table (or NULL)")
print("   3. All monetary fields use DECIMAL, not strings")
print("   4. Dates in 'YYYY-MM-DD' format")
print("   5. gross_pay >= 0, net_pay should be >= 0 (if constraint enabled)")

cur.close()
conn.close()
