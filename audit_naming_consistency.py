#!/usr/bin/env python3
"""Comprehensive audit of table and column naming consistency across codebase"""
import psycopg2
import re
from pathlib import Path
from collections import defaultdict

# Connect to database
conn = psycopg2.connect('dbname=almsdata user=postgres password=ArrowLimousine host=localhost')
cur = conn.cursor()

print("=" * 80)
print("DATABASE SCHEMA AUDIT")
print("=" * 80)

# Get all tables
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_type = 'BASE TABLE'
    ORDER BY table_name
""")
tables = [row[0] for row in cur.fetchall()]

print(f"\n{len(tables)} TABLES FOUND:")
print("-" * 80)
for table in tables:
    print(f"  - {table}")

# Get columns for key tables
key_tables = ['receipts', 'charters', 'banking_transactions', 'vehicles', 
              'employees', 'customers', 'payments', 'charter_charges']

print("\n" + "=" * 80)
print("KEY TABLE COLUMNS")
print("=" * 80)

table_columns = {}
for table in key_tables:
    if table not in tables:
        print(f"\n⚠️  TABLE NOT FOUND: {table}")
        continue
    
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
        ORDER BY ordinal_position
    """, (table,))
    
    cols = cur.fetchall()
    table_columns[table] = cols
    
    print(f"\n{table.upper()} ({len(cols)} columns):")
    print("-" * 80)
    for col, dtype, nullable in cols:
        null_str = "NULL" if nullable == "YES" else "NOT NULL"
        print(f"  {col:<35} {dtype:<20} {null_str}")

# Check for common naming issues
print("\n" + "=" * 80)
print("POTENTIAL NAMING INCONSISTENCIES")
print("=" * 80)

issues = []

# Check receipts table for ID field inconsistencies
if 'receipts' in table_columns:
    receipt_cols = [col[0] for col in table_columns['receipts']]
    
    # Check for charter reference
    if 'charter_id' in receipt_cols:
        print("\n✓ receipts.charter_id exists")
    else:
        issues.append("✗ receipts.charter_id MISSING")
    
    # Check for vehicle reference
    if 'vehicle_id' in receipt_cols:
        print("✓ receipts.vehicle_id exists")
    else:
        issues.append("✗ receipts.vehicle_id MISSING")
    
    # Check for employee reference
    if 'employee_id' in receipt_cols:
        print("✓ receipts.employee_id exists")
    else:
        issues.append("✗ receipts.employee_id MISSING")
    
    # Check for banking reference
    if 'banking_transaction_id' in receipt_cols:
        print("✓ receipts.banking_transaction_id exists")
    else:
        issues.append("✗ receipts.banking_transaction_id MISSING")

# Check charters table
if 'charters' in table_columns:
    charter_cols = [col[0] for col in table_columns['charters']]
    
    if 'charter_id' in charter_cols:
        print("✓ charters.charter_id exists")
    else:
        issues.append("✗ charters.charter_id MISSING")
    
    if 'reserve_number' in charter_cols:
        print("✓ charters.reserve_number exists")
    else:
        issues.append("✗ charters.reserve_number MISSING")
    
    if 'customer_id' in charter_cols:
        print("✓ charters.customer_id exists")
    else:
        issues.append("✗ charters.customer_id MISSING")

# Check banking_transactions table
if 'banking_transactions' in table_columns:
    banking_cols = [col[0] for col in table_columns['banking_transactions']]
    
    if 'transaction_id' in banking_cols:
        print("✓ banking_transactions.transaction_id exists")
    else:
        issues.append("✗ banking_transactions.transaction_id MISSING")
    
    if 'receipt_id' in banking_cols:
        print("✓ banking_transactions.receipt_id exists")
    else:
        issues.append("✗ banking_transactions.receipt_id MISSING")

if issues:
    print("\n" + "⚠️  ISSUES FOUND:")
    for issue in issues:
        print(f"  {issue}")
else:
    print("\n✓ No critical column issues found")

conn.close()

print("\n" + "=" * 80)
print("AUDIT COMPLETE")
print("=" * 80)
