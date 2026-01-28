#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check for Centratech in vendor tables added today (Dec 8, 2025)."""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 120)
print("CENTRATECH TECHNICAL SERVICES - VENDOR DATABASE CHECK")
print("=" * 120)
print()

# Check main vendor tables
tables_to_check = [
    ('vendors', ['vendor_name', 'category']),
    ('vendor_standardization', ['raw_vendor_name', 'standardized_vendor_name', 'category']),
    ('vendor_name_mapping', ['raw_name', 'standardized_name', 'category']),
    ('vendor_default_categories', ['vendor_pattern', 'default_category']),
    ('suppliers', ['supplier_name', 'category'])
]

for table_name, search_columns in tables_to_check:
    print(f"\n{'='*120}")
    print(f"TABLE: {table_name}")
    print('='*120)
    
    # Get table schema
    cur.execute(f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = '{table_name}'
        ORDER BY ordinal_position
    """)
    schema = cur.fetchall()
    
    if not schema:
        print(f"  ✗ Table does not exist")
        continue
    
    # Check which columns exist
    available_cols = {col[0] for col in schema}
    
    # Find the name column
    name_col = None
    for col in search_columns:
        if col in available_cols:
            name_col = col
            break
    
    if not name_col:
        print(f"  ✗ No vendor name column found. Available columns: {', '.join(available_cols)}")
        continue
    
    # Check for timestamp columns
    timestamp_col = None
    for col in ['created_at', 'updated_at', 'created_date', 'modified_date', 'date_added']:
        if col in available_cols:
            timestamp_col = col
            break
    
    # Query for Centratech entries
    try:
        if timestamp_col:
            cur.execute(f"""
                SELECT *, {timestamp_col}::text as timestamp
                FROM {table_name}
                WHERE {name_col} ILIKE '%centratech%'
                   OR {name_col} ILIKE '%centra%tech%'
                ORDER BY {timestamp_col} DESC
            """)
        else:
            cur.execute(f"""
                SELECT *
                FROM {table_name}
                WHERE {name_col} ILIKE '%centratech%'
                   OR {name_col} ILIKE '%centra%tech%'
            """)
        
        results = cur.fetchall()
        col_names = [desc[0] for desc in cur.description]
        
        if results:
            print(f"  ✓ Found {len(results)} Centratech entries\n")
            for row in results:
                # Format output
                row_dict = dict(zip(col_names, row))
                print(f"  Entry:")
                for col_name, value in row_dict.items():
                    if col_name == 'timestamp':
                        # Highlight if created today
                        if value and '2025-12-08' in str(value):
                            print(f"    {col_name:25s}: {value} ⭐ CREATED TODAY")
                        else:
                            print(f"    {col_name:25s}: {value}")
                    else:
                        print(f"    {col_name:25s}: {value}")
                print()
        else:
            print(f"  ✗ No Centratech entries found")
    
    except Exception as e:
        print(f"  ✗ Error querying table: {e}")

print("\n" + "="*120)
print("SUMMARY")
print("="*120)

cur.close()
conn.close()
