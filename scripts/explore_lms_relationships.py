#!/usr/bin/env python3
"""
Extract payment-reserve linkages from LMS relationship tables.

LMS structure:
- Payment table: Has PaymentID, Amount, etc. (may not have Reserve_No directly)
- Relationship/Link table: Maps PaymentID → Reserve_Number
"""

import pyodbc
import psycopg2

LMS_PATH = r'L:\New folder\lms.mdb'

def get_lms_connection():
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

def list_all_tables(conn):
    cur = conn.cursor()
    tables = [t.table_name for t in cur.tables(tableType='TABLE')]
    return tables

def explore_table_structure(conn, table_name):
    """Get columns and sample data from a table"""
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT TOP 5 * FROM [{table_name}]")
        columns = [col[0] for col in cur.description]
        rows = cur.fetchall()
        
        cur.execute(f"SELECT COUNT(*) FROM [{table_name}]")
        count = cur.fetchone()[0]
        
        return columns, rows, count
    except Exception as e:
        return None, None, 0

print("="*80)
print("LMS RELATIONSHIP TABLE EXPLORER")
print("="*80)

try:
    conn = get_lms_connection()
    print(f"\n✅ Connected to LMS: {LMS_PATH}")
except Exception as e:
    print(f"\n❌ Failed to connect: {e}")
    exit(1)

# List all tables
tables = list_all_tables(conn)
print(f"\n📊 Found {len(tables)} tables in LMS\n")

# Look for relationship/link tables
print("🔍 Searching for relationship/link tables:")
for table in sorted(tables):
    # Check if it might be a relationship table
    if any(word in table.lower() for word in ['link', 'rel', 'match', 'assoc', 'map']):
        cols, rows, count = explore_table_structure(conn, table)
        if cols:
            print(f"\n   📋 {table} ({count:,} records)")
            print(f"      Columns: {', '.join(cols)}")
            if rows:
                print(f"      Sample data:")
                for row in rows[:3]:
                    print(f"         {row}")

# Check Payment table structure
print(f"\n" + "="*80)
print("PAYMENT TABLE ANALYSIS")
print("="*80)
if 'Payment' in tables:
    cols, rows, count = explore_table_structure(conn, 'Payment')
    print(f"\n💰 Payment table ({count:,} records)")
    print(f"   Columns: {', '.join(cols)}")
    print(f"\n   Sample records:")
    for i, row in enumerate(rows[:5], 1):
        print(f"   {i}. {row}")

# Check E_Payment table
if 'E_Payment' in tables:
    cols, rows, count = explore_table_structure(conn, 'E_Payment')
    print(f"\n📧 E_Payment table ({count:,} records)")
    print(f"   Columns: {', '.join(cols)}")
    if rows:
        print(f"\n   Sample records:")
        for i, row in enumerate(rows[:5], 1):
            print(f"   {i}. {row}")

# List ALL tables with their record counts
print(f"\n" + "="*80)
print("ALL LMS TABLES")
print("="*80)
print(f"\n{'Table Name':<40} {'Records':<15} {'Key Columns'}")
print("-"*80)
for table in sorted(tables):
    cols, rows, count = explore_table_structure(conn, table)
    if cols:
        # Look for ID/key columns
        key_cols = [c for c in cols if any(word in c.lower() for word in ['id', 'no', 'key', 'reserve', 'payment', 'account'])]
        key_str = ', '.join(key_cols[:4]) if key_cols else ''
        print(f"{table:<40} {count:<15,} {key_str}")

conn.close()

print("\n" + "="*80)
print("EXPLORATION COMPLETE")
print("="*80)
print("\n💡 Look for tables with both PaymentID and Reserve_No/Reserve_Number columns")
