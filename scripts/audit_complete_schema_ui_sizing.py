#!/usr/bin/env python3
"""
Comprehensive database schema audit for ALL tables
- Column names, types, nullability
- Actual max data lengths from database
- UI sizing recommendations grouped by type
- Generate reference card for form design
"""
import os
import psycopg2
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

try:
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Get all user tables (exclude system tables)
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    
    tables = [row[0] for row in cur.fetchall()]
    
    output = []
    output.append("=" * 200)
    output.append("COMPLETE DATABASE SCHEMA REFERENCE - UI SIZING GUIDE")
    output.append("=" * 200)
    output.append(f"Total Tables: {len(tables)}\n")
    
    all_columns = []
    
    for table_name in tables:
        output.append(f"\n{'='*200}")
        output.append(f"TABLE: {table_name}")
        output.append(f"{'='*200}")
        
        # Get columns
        cur.execute("""
            SELECT column_name, data_type, is_nullable, character_maximum_length, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        
        columns = cur.fetchall()
        
        # Group by type
        type_groups = defaultdict(list)
        
        for col_name, data_type, is_nullable, char_max_len, num_prec, num_scale in columns:
            # Determine group
            if data_type in ('character varying', 'text'):
                group = 'TEXT/VARCHAR'
            elif data_type == 'date':
                group = 'DATE'
            elif data_type in ('numeric', 'double precision', 'real'):
                group = 'NUMERIC'
            elif data_type == 'boolean':
                group = 'BOOLEAN'
            elif data_type in ('integer', 'serial', 'bigint', 'smallint'):
                group = 'INTEGER'
            elif 'timestamp' in data_type:
                group = 'TIMESTAMP'
            else:
                group = 'OTHER'
            
            # Get actual max length from data
            actual_max_len = 0
            sample_val = ""
            
            if data_type in ('character varying', 'text'):
                try:
                    cur.execute(f"""
                        SELECT MAX(CHAR_LENGTH("{col_name}"::text)) as max_len
                        FROM "{table_name}"
                        WHERE "{col_name}" IS NOT NULL
                    """)
                    result = cur.fetchone()
                    actual_max_len = result[0] if result[0] else 0
                    
                    # Get sample
                    if actual_max_len > 0:
                        cur.execute(f"""
                            SELECT "{col_name}"
                            FROM "{table_name}"
                            WHERE "{col_name}" IS NOT NULL
                            ORDER BY CHAR_LENGTH("{col_name}"::text) DESC
                            LIMIT 1
                        """)
                        sample = cur.fetchone()
                        sample_val = str(sample[0])[:50] if sample else ""
                except:
                    pass
            
            type_groups[group].append({
                'name': col_name,
                'data_type': data_type,
                'nullable': is_nullable,
                'char_max': char_max_len,
                'actual_max': actual_max_len,
                'sample': sample_val,
                'numeric_prec': num_prec,
                'numeric_scale': num_scale
            })
            
            all_columns.append({
                'table': table_name,
                'name': col_name,
                'data_type': data_type,
                'nullable': is_nullable,
                'actual_max': actual_max_len
            })
        
        # Output grouped by type
        for group_name in ['TEXT/VARCHAR', 'DATE', 'NUMERIC', 'BOOLEAN', 'INTEGER', 'TIMESTAMP', 'OTHER']:
            if group_name in type_groups:
                cols = type_groups[group_name]
                output.append(f"\n  {group_name} ({len(cols)} columns):")
                output.append("-" * 200)
                
                for col in cols:
                    nullable = "NULL" if col['nullable'] == 'YES' else "NOTNULL"
                    
                    if col['data_type'] in ('character varying', 'text'):
                        declared = f"({col['char_max']})" if col['char_max'] else ""
                        actual = f"Actual max: {col['actual_max']}"
                        sample = f"Sample: {col['sample'][:40]}" if col['sample'] else ""
                        output.append(f"    {col['name']:35s} {col['data_type']:20s}{declared:10s} {nullable:10s} {actual:20s} {sample}")
                    elif col['data_type'] == 'numeric':
                        prec = f"({col['numeric_prec']},{col['numeric_scale']})" if col['numeric_prec'] else ""
                        output.append(f"    {col['name']:35s} {col['data_type']:20s}{prec:10s} {nullable:10s}")
                    else:
                        output.append(f"    {col['name']:35s} {col['data_type']:20s} {nullable:10s}")
    
    # Summary and recommendations
    output.append(f"\n{'='*200}")
    output.append("UI SIZING RECOMMENDATIONS BY DATA TYPE")
    output.append(f"{'='*200}")
    output.append("""
TEXT/VARCHAR FIELDS:
  Length 0-30       → Single-line input box (width: 30-40 pixels)
  Length 31-100     → Single-line input box (width: 80-100 pixels)
  Length 101-500    → Multi-line textarea (width: 100%, height: 3-4 rows, word-wrap enabled)
  Length > 500      → Large textarea (width: 100%, height: 6-10 rows, scrollbar enabled)

DATE FIELDS:
  → Standard date picker (fixed width: 120-150 pixels, dropdown calendar)
  → Format: YYYY-MM-DD

NUMERIC FIELDS:
  → Spinner input (fixed width: 80-120 pixels)
  → Include +/- buttons for increment/decrement
  → Show decimal places as defined in schema (e.g., DECIMAL(12,2))

BOOLEAN FIELDS:
  → Checkbox (fixed width: 20-30 pixels)
  OR Toggle switch (fixed width: 50-60 pixels)

INTEGER FIELDS:
  → Numeric input (fixed width: 80-120 pixels)
  → No decimal places allowed

TIMESTAMP FIELDS:
  → Date + time picker (fixed width: 180-200 pixels)
  → Format: YYYY-MM-DD HH:MM:SS

LAYOUT GUIDELINES:
  ✓ Group related fields by type on same horizontal line when possible
  ✓ Use fixed widths - NO auto-width (prevents layout shift)
  ✓ Label above or to the left of field (consistent positioning)
  ✓ Maintain vertical alignment for easy reading and printing
  ✓ Use field type-specific widgets (date picker, numeric spinner, etc.)
  ✓ Multi-line fields should have visible scroll indicators
  ✓ Print-friendly: 8.5"x11" page = ~100 pixels = ~15 characters per line
  ✓ Leave space for printing without resizing
    """)
    
    # Write to file
    with open('reports/COMPLETE_SCHEMA_UI_SIZING_REFERENCE.txt', 'w') as f:
        f.write('\n'.join(output))
    
    print('\n'.join(output[:100]))  # Print first 100 lines to terminal
    print(f"\n... (full report saved to reports/COMPLETE_SCHEMA_UI_SIZING_REFERENCE.txt)")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    if conn:
        conn.close()
