#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 1: Compare ALMS clients table schema against legacy LMS/LIMO tables.
Determine what customer information exists in ALMS and what's missing.
"""
import psycopg2
import json

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

print("="*80)
print("STEP 1: CUSTOMER DATA COMPLETENESS AUDIT")
print("="*80)

# Get all columns from clients table
print("\n📋 ALMS TABLE: clients")
print("-" * 80)
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'clients'
    ORDER BY ordinal_position
""")
clients_cols = cur.fetchall()
print(f"Total columns: {len(clients_cols)}\n")
for col, dtype, nullable in clients_cols:
    null_str = "NULL" if nullable == "YES" else "NOT NULL"
    print(f"  {col:<30} {dtype:<20} {null_str}")

# Get all columns from limo_clients table
print("\n\n📋 LEGACY TABLE: limo_clients")
print("-" * 80)
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'limo_clients'
    ORDER BY ordinal_position
""")
limo_cols = cur.fetchall()
print(f"Total columns: {len(limo_cols)}\n")
for col, dtype, nullable in limo_cols:
    null_str = "NULL" if nullable == "YES" else "NOT NULL"
    print(f"  {col:<30} {dtype:<20} {null_str}")

# Get all columns from lms_customers_enhanced table
print("\n\n📋 LEGACY TABLE: lms_customers_enhanced")
print("-" * 80)
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'lms_customers_enhanced'
    ORDER BY ordinal_position
""")
lms_enh_cols = cur.fetchall()
print(f"Total columns: {len(lms_enh_cols)}\n")
for col, dtype, nullable in lms_enh_cols:
    null_str = "NULL" if nullable == "YES" else "NOT NULL"
    print(f"  {col:<30} {dtype:<20} {null_str}")

# Extract column names for comparison
clients_col_names = {col[0] for col in clients_cols}
limo_col_names = {col[0] for col in limo_cols}
lms_enh_col_names = {col[0] for col in lms_enh_cols}

print("\n" + "="*80)
print("COLUMN COVERAGE ANALYSIS")
print("="*80)

# What's in limo_clients but NOT in clients?
limo_unique = limo_col_names - clients_col_names
if limo_unique:
    print(f"\n⚠️  Columns ONLY in limo_clients (not in ALMS clients):")
    for col in sorted(limo_unique):
        print(f"   - {col}")
else:
    print(f"\n✅ limo_clients: All columns either in ALMS clients or can be dropped")

# What's in lms_customers_enhanced but NOT in clients?
lms_unique = lms_enh_col_names - clients_col_names
if lms_unique:
    print(f"\n⚠️  Columns ONLY in lms_customers_enhanced (not in ALMS clients):")
    for col in sorted(lms_unique):
        print(f"   - {col}")
else:
    print(f"\n✅ lms_customers_enhanced: All columns either in ALMS clients or can be dropped")

# Data volume check
print("\n" + "="*80)
print("DATA VOLUME COMPARISON")
print("="*80)

cur.execute("SELECT COUNT(*) FROM clients")
clients_count = cur.fetchone()[0]
print(f"clients table: {clients_count:,} records")

cur.execute("SELECT COUNT(*) FROM limo_clients")
limo_count = cur.fetchone()[0]
print(f"limo_clients table: {limo_count:,} records")

cur.execute("SELECT COUNT(*) FROM lms_customers_enhanced")
lms_count = cur.fetchone()[0]
print(f"lms_customers_enhanced table: {lms_count:,} records")

cur.close()
conn.close()
