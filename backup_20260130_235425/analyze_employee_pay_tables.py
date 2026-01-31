#!/usr/bin/env python3
"""
Analyze employee pay/payroll related tables in the database.
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("="*80)
print("EMPLOYEE PAY/PAYROLL TABLES ANALYSIS")
print("="*80)

# Find all employee/payroll related tables
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_type = 'BASE TABLE'
    AND (
        table_name ILIKE '%employee%' 
        OR table_name ILIKE '%payroll%'
        OR table_name ILIKE '%pay%'
        OR table_name ILIKE '%wage%'
        OR table_name ILIKE '%salary%'
        OR table_name ILIKE '%driver%'
        OR table_name ILIKE '%t4%'
        OR table_name ILIKE '%earnings%'
    )
    ORDER BY table_name
""")

tables = [row[0] for row in cur.fetchall()]

print(f"\nFound {len(tables)} employee/pay related tables:")
print("-"*80)

for table in tables:
    # Get row count
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    
    # Get column count
    cur.execute(f"""
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_name = '{table}'
    """)
    col_count = cur.fetchone()[0]
    
    print(f"\n{table}")
    print(f"  Rows: {count:,}")
    print(f"  Columns: {col_count}")
    
    # Get column details
    cur.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table}'
        ORDER BY ordinal_position
    """)
    
    columns = cur.fetchall()
    print(f"  Structure:")
    for col_name, col_type in columns:
        print(f"    {col_name:<30} {col_type}")

# Categorize tables
print("\n" + "="*80)
print("CATEGORIZATION")
print("="*80)

pay_tables = [t for t in tables if 'pay' in t.lower() and 'payment' not in t.lower()]
employee_tables = [t for t in tables if 'employee' in t.lower()]
driver_tables = [t for t in tables if 'driver' in t.lower() and 'driver_pay' not in [x.lower() for x in employee_tables]]
payroll_tables = [t for t in tables if 'payroll' in t.lower()]
t4_tables = [t for t in tables if 't4' in t.lower()]

print(f"\nPay/Earnings tables ({len(pay_tables)}):")
for t in pay_tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    count = cur.fetchone()[0]
    print(f"  {t:<40} {count:>8,} rows")

print(f"\nEmployee tables ({len(employee_tables)}):")
for t in employee_tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    count = cur.fetchone()[0]
    print(f"  {t:<40} {count:>8,} rows")

print(f"\nDriver tables ({len(driver_tables)}):")
for t in driver_tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    count = cur.fetchone()[0]
    print(f"  {t:<40} {count:>8,} rows")

print(f"\nPayroll tables ({len(payroll_tables)}):")
for t in payroll_tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    count = cur.fetchone()[0]
    print(f"  {t:<40} {count:>8,} rows")

print(f"\nT4/Tax tables ({len(t4_tables)}):")
for t in t4_tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    count = cur.fetchone()[0]
    print(f"  {t:<40} {count:>8,} rows")

# Check for foreign key relationships
print("\n" + "="*80)
print("POTENTIAL CONSOLIDATION OPPORTUNITIES")
print("="*80)

# Find empty tables
empty_tables = []
for table in tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    if count == 0:
        empty_tables.append(table)

if empty_tables:
    print(f"\nEmpty tables (candidates for deletion):")
    for t in empty_tables:
        print(f"  - {t}")

# Find very small tables (< 10 rows)
small_tables = []
for table in tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    if 0 < count < 10:
        small_tables.append((table, count))

if small_tables:
    print(f"\nVery small tables (< 10 rows):")
    for t, count in small_tables:
        print(f"  - {t:<40} {count} rows")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Total employee/pay tables: {len(tables)}")
print(f"Empty tables: {len(empty_tables)}")
print(f"Small tables (< 10 rows): {len(small_tables)}")
print(f"Active tables: {len(tables) - len(empty_tables)}")

cur.close()
conn.close()
