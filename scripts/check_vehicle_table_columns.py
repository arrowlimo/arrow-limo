#!/usr/bin/env python
"""Check vehicles table for repeating/duplicate columns."""

import psycopg2
import os
from collections import Counter

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("\n" + "=" * 100)
print("VEHICLES TABLE COLUMN ANALYSIS")
print("=" * 100)

# Get all columns from vehicles table
cur.execute("""
    SELECT 
        column_name,
        data_type,
        character_maximum_length,
        is_nullable,
        column_default,
        ordinal_position
    FROM information_schema.columns
    WHERE table_schema = 'public'
    AND table_name = 'vehicles'
    ORDER BY ordinal_position
""")

columns = cur.fetchall()

print(f"\nTotal columns: {len(columns)}")
print("\n" + "-" * 100)
print(f"{'#':<4} {'Column Name':<30} {'Data Type':<20} {'Length':<8} {'Nullable':<10} {'Default':<20}")
print("-" * 100)

column_names = []
for col in columns:
    col_name, data_type, max_len, nullable, default, position = col
    column_names.append(col_name)
    
    length_str = str(max_len) if max_len else "N/A"
    nullable_str = "YES" if nullable == 'YES' else "NO"
    default_str = str(default)[:18] if default else "None"
    
    print(f"{position:<4} {col_name:<30} {data_type:<20} {length_str:<8} {nullable_str:<10} {default_str:<20}")

# Check for duplicate column names
print("\n" + "=" * 100)
print("DUPLICATE COLUMN NAME CHECK")
print("=" * 100)

column_counts = Counter(column_names)
duplicates = {name: count for name, count in column_counts.items() if count > 1}

if duplicates:
    print("\n⚠️  DUPLICATE COLUMNS FOUND:")
    for col_name, count in duplicates.items():
        print(f"  - '{col_name}' appears {count} times")
        
        # Get details of each duplicate
        cur.execute("""
            SELECT ordinal_position, data_type, character_maximum_length, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'vehicles'
            AND column_name = %s
            ORDER BY ordinal_position
        """, (col_name,))
        
        dup_details = cur.fetchall()
        for pos, dtype, max_len, nullable in dup_details:
            print(f"    Position {pos}: {dtype}({max_len or 'N/A'}), Nullable: {nullable}")
else:
    print("\n✅ NO DUPLICATE COLUMN NAMES - All columns are unique")

# Check for similar column names (potential typos or variants)
print("\n" + "=" * 100)
print("SIMILAR COLUMN NAME CHECK")
print("=" * 100)

similar_groups = {}
for i, col1 in enumerate(column_names):
    for col2 in column_names[i+1:]:
        # Check for similar patterns
        if col1.replace('_', '').lower() == col2.replace('_', '').lower():
            key = f"{col1} <-> {col2}"
            similar_groups[key] = "Same name, different underscores"
        elif col1.lower() in col2.lower() or col2.lower() in col1.lower():
            if abs(len(col1) - len(col2)) <= 3:  # Similar length
                key = f"{col1} <-> {col2}"
                similar_groups[key] = "Similar substring"

if similar_groups:
    print("\n⚠️  SIMILAR COLUMN NAMES FOUND:")
    for pair, reason in similar_groups.items():
        print(f"  - {pair}: {reason}")
else:
    print("\n✅ NO SIMILAR COLUMN NAMES - All column names are distinct")

# Check for common duplicate patterns
print("\n" + "=" * 100)
print("COMMON PATTERN CHECK")
print("=" * 100)

common_patterns = [
    ('id', 'vehicle_id'),
    ('number', 'vehicle_number'),
    ('type', 'vehicle_type'),
    ('make', 'manufacturer'),
    ('model', 'vehicle_model'),
    ('year', 'model_year'),
    ('vin', 'vin_number'),
    ('plate', 'license_plate'),
    ('created', 'created_at'),
    ('updated', 'updated_at'),
]

found_patterns = []
for pattern1, pattern2 in common_patterns:
    cols_with_pattern1 = [c for c in column_names if pattern1 in c.lower()]
    cols_with_pattern2 = [c for c in column_names if pattern2 in c.lower()]
    
    if cols_with_pattern1 and cols_with_pattern2:
        found_patterns.append({
            'pattern1': pattern1,
            'columns1': cols_with_pattern1,
            'pattern2': pattern2,
            'columns2': cols_with_pattern2
        })

if found_patterns:
    print("\n⚠️  COLUMNS WITH OVERLAPPING CONCEPTS:")
    for item in found_patterns:
        print(f"\n  Pattern '{item['pattern1']}':")
        for col in item['columns1']:
            print(f"    - {col}")
        print(f"  Pattern '{item['pattern2']}':")
        for col in item['columns2']:
            print(f"    - {col}")
else:
    print("\n✅ NO OVERLAPPING PATTERNS FOUND")

# Check for timestamp/date columns
print("\n" + "=" * 100)
print("TIMESTAMP COLUMNS")
print("=" * 100)

cur.execute("""
    SELECT column_name, data_type, column_default
    FROM information_schema.columns
    WHERE table_schema = 'public'
    AND table_name = 'vehicles'
    AND (data_type LIKE '%timestamp%' OR data_type LIKE '%date%')
    ORDER BY ordinal_position
""")

timestamp_cols = cur.fetchall()
if timestamp_cols:
    print(f"\nFound {len(timestamp_cols)} timestamp/date columns:")
    for col_name, data_type, default in timestamp_cols:
        print(f"  - {col_name}: {data_type} (default: {default or 'None'})")
else:
    print("\nNo timestamp/date columns found")

print("\n" + "=" * 100)

cur.close()
conn.close()
