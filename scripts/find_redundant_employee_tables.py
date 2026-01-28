#!/usr/bin/env python3
"""
Find all employee/pay related tables and identify redundant ones.
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
print("EMPLOYEE PAY TABLE AUDIT - FIND REDUNDANT TABLES")
print("="*90)

# Find all employee/pay related tables
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE'
    AND (
        table_name LIKE '%employee%'
        OR table_name LIKE '%pay%'
        OR table_name LIKE '%payroll%'
        OR table_name LIKE '%driver%'
        OR table_name LIKE '%t4%'
        OR table_name LIKE '%roe%'
        OR table_name LIKE '%wage%'
        OR table_name LIKE '%salary%'
    )
    ORDER BY table_name
""")

tables = [row[0] for row in cur.fetchall()]

print(f"\nFound {len(tables)} employee/pay related tables:\n")

# Categorize tables
categories = {
    'Core Active': [],
    'Empty (0 rows)': [],
    'Very Small (<10 rows)': [],
    'Small (10-100 rows)': [],
    'Medium (100-1000 rows)': [],
    'Large (1000+ rows)': []
}

table_info = []

for table in tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    row_count = cur.fetchone()[0]
    
    # Get column count
    cur.execute(f"""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = '{table}'
    """)
    col_count = cur.fetchone()[0]
    
    table_info.append({
        'name': table,
        'rows': row_count,
        'cols': col_count
    })
    
    if row_count == 0:
        categories['Empty (0 rows)'].append(table)
    elif row_count < 10:
        categories['Very Small (<10 rows)'].append(table)
    elif row_count < 100:
        categories['Small (10-100 rows)'].append(table)
    elif row_count < 1000:
        categories['Medium (100-1000 rows)'].append(table)
    else:
        categories['Large (1000+ rows)'].append(table)

# Print by category
for category, tables_list in categories.items():
    if tables_list:
        print(f"\n{category}:")
        print("-" * 90)
        for table in tables_list:
            info = next(t for t in table_info if t['name'] == table)
            print(f"   {table:<45} {info['rows']:>8,} rows, {info['cols']:>3} cols")

# Identify likely redundant tables
print("\n" + "="*90)
print("REDUNDANCY ANALYSIS")
print("="*90)

redundant = []
core = ['employees', 'employee_pay_master', 'driver_payroll', 'pay_periods', 
        'employee_t4_summary', 'employee_roe_records']

print(f"\nCore tables (keep these):")
for table in core:
    if table in [t['name'] for t in table_info]:
        info = next(t for t in table_info if t['name'] == table)
        print(f"   ✅ {table:<45} {info['rows']:>8,} rows")

print(f"\nLikely redundant tables:")
print("-" * 90)

for table in table_info:
    if table['name'] not in core:
        status = ""
        if table['rows'] == 0:
            status = "Empty - safe to drop"
            redundant.append(table['name'])
        elif table['rows'] < 10 and 'staging' in table['name']:
            status = "Staging table, nearly empty"
            redundant.append(table['name'])
        elif table['rows'] < 10 and 'temp' in table['name']:
            status = "Temp table, nearly empty"
            redundant.append(table['name'])
        elif 'backup' in table['name']:
            status = "Backup table - review before dropping"
        elif 'old' in table['name']:
            status = "Old table - review before dropping"
        
        if status:
            print(f"   {table['name']:<45} {table['rows']:>8,} rows - {status}")

print(f"\n" + "="*90)
print("SUMMARY")
print("="*90)
print(f"Total employee/pay tables: {len(tables)}")
print(f"Core tables (keep): {len(core)}")
print(f"Redundant candidates: {len(redundant)}")

if redundant:
    print(f"\n⚠️  Redundant tables to review:")
    for table in redundant:
        print(f"   - {table}")

cur.close()
conn.close()
