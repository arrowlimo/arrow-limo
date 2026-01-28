#!/usr/bin/env python3
"""
Audit employees table data types and actual data lengths
Generate sizing guide for UI form design
"""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

try:
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 120)
    print("EMPLOYEES TABLE: Column Types and Data Lengths")
    print("=" * 120)
    
    # Get all columns with their types
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'employees'
        ORDER BY ordinal_position
    """)
    
    columns = cur.fetchall()
    
    results = []
    
    for col_name, data_type, is_nullable in columns:
        # Get max length for text columns
        if data_type in ('character varying', 'text'):
            cur.execute(f"""
                SELECT MAX(CHAR_LENGTH({col_name})) as max_len, 
                       COUNT(*) FILTER (WHERE {col_name} IS NOT NULL) as non_null_count
                FROM employees
            """)
            max_len, non_null_count = cur.fetchone()
            max_len = max_len or 0
            
            # Get sample values for non-null text fields
            if non_null_count > 0:
                cur.execute(f"""
                    SELECT {col_name}
                    FROM employees
                    WHERE {col_name} IS NOT NULL
                    ORDER BY CHAR_LENGTH({col_name}) DESC
                    LIMIT 1
                """)
                sample = cur.fetchone()[0] if cur.fetchone() else ""
                cur.execute(f"""
                    SELECT {col_name}
                    FROM employees
                    WHERE {col_name} IS NOT NULL
                    ORDER BY CHAR_LENGTH({col_name}) DESC
                    LIMIT 1
                """)
                sample = cur.fetchone()[0] if cur.fetchone() is not None else ""
            else:
                sample = ""
        else:
            max_len = None
            sample = ""
        
        results.append((col_name, data_type, is_nullable, max_len, sample))
    
    # Group by type
    type_groups = {
        'TEXT/VARCHAR': [],
        'DATE': [],
        'NUMERIC': [],
        'BOOLEAN': [],
        'INTEGER': [],
        'TIMESTAMP': []
    }
    
    for col_name, data_type, is_nullable, max_len, sample in results:
        if data_type in ('character varying', 'text'):
            group = 'TEXT/VARCHAR'
        elif data_type == 'date':
            group = 'DATE'
        elif data_type in ('numeric', 'double precision'):
            group = 'NUMERIC'
        elif data_type == 'boolean':
            group = 'BOOLEAN'
        elif data_type in ('integer', 'serial', 'bigint'):
            group = 'INTEGER'
        elif 'timestamp' in data_type:
            group = 'TIMESTAMP'
        else:
            group = 'OTHER'
        
        if group in type_groups:
            type_groups[group].append((col_name, data_type, is_nullable, max_len, sample))
    
    # Print grouped by type
    for group_name, cols in type_groups.items():
        if cols:
            print(f"\n{group_name} FIELDS ({len(cols)}):")
            print("-" * 120)
            for col_name, data_type, is_nullable, max_len, sample in cols:
                nullable = "NULL" if is_nullable == 'YES' else "NOT NULL"
                if max_len is not None:
                    print(f"  {col_name:35s} {data_type:20s} {nullable:10s} Max Length: {max_len:5d}  Sample: {str(sample)[:40]}")
                else:
                    print(f"  {col_name:35s} {data_type:20s} {nullable:10s}")
    
    # Summary
    print("\n" + "=" * 120)
    print("UI SIZING RECOMMENDATIONS:")
    print("=" * 120)
    print("\nTEXT FIELDS:")
    print("  < 50 chars   → Single-line text box (width: 40-50)")
    print("  50-500 chars → Multi-line text area (height: 3-4 rows)")
    print("  > 500 chars  → Large text area with scroll (height: 6-8 rows)")
    print("\nDATE FIELDS:")
    print("  → Standard date picker (fixed width)")
    print("\nNUMERIC FIELDS:")
    print("  → Numeric input with spinner (fixed width)")
    print("\nBOOLEAN FIELDS:")
    print("  → Checkbox or toggle (fixed width)")
    print("\nINTEGER FIELDS:")
    print("  → Numeric input (fixed width)")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    if conn:
        conn.close()
