#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check for vendor-related tables and Centratech entries."""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Find vendor-related tables
print("=" * 100)
print("VENDOR-RELATED TABLES IN DATABASE")
print("=" * 100)

cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND (table_name LIKE '%vendor%' OR table_name LIKE '%supplier%')
    ORDER BY table_name
""")

vendor_tables = cur.fetchall()
if vendor_tables:
    for table in vendor_tables:
        print(f"  - {table[0]}")
else:
    print("  No vendor-specific tables found")

print()

# Check for Centratech in any vendor tables found
if vendor_tables:
    print("=" * 100)
    print("CHECKING FOR CENTRATECH IN VENDOR TABLES")
    print("=" * 100)
    
    for table in vendor_tables:
        table_name = table[0]
        print(f"\nTable: {table_name}")
        print("-" * 100)
        
        # Get columns to check for timestamps
        cur.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
            AND column_name IN ('created_at', 'updated_at', 'created_date', 'modified_date')
        """)
        timestamp_cols = [row[0] for row in cur.fetchall()]
        
        # Get all columns
        cur.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """)
        all_cols = [row[0] for row in cur.fetchall()]
        
        # Build query
        timestamp_select = ", ".join(timestamp_cols) if timestamp_cols else "'no_timestamp'"
        cur.execute(f"""
            SELECT *, {timestamp_select} as timestamp_info
            FROM {table_name}
            WHERE vendor_name ILIKE '%centratech%' 
               OR vendor_name ILIKE '%centra%tech%'
            ORDER BY {timestamp_cols[0] if timestamp_cols else all_cols[0]} DESC
        """)
        
        results = cur.fetchall()
        if results:
            print(f"Found {len(results)} Centratech entries:")
            for row in results:
                print(f"  {row}")
        else:
            print("  No Centratech entries found")

cur.close()
conn.close()
