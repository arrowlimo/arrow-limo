#!/usr/bin/env python3
"""
Check staging tables status in almsdata database
Identify what data is staged and ready for promotion to main tables

Created: 2025-10-31
"""

import psycopg2
import os

def check_staging_status():
    """Check status of all staging tables."""
    
    # Database connection
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("ALMSDATA STAGING TABLES STATUS CHECK")
    print("=" * 80)
    print()
    
    # Find all staging tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE '%staging%'
        ORDER BY table_name
    """)
    
    staging_tables = [row[0] for row in cur.fetchall()]
    
    print(f"Found {len(staging_tables)} staging tables:")
    print()
    
    for table in staging_tables:
        print(f"\n{'='*80}")
        print(f"TABLE: {table}")
        print('='*80)
        
        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"Total Records: {count:,}")
        
        if count == 0:
            print("Status: EMPTY - No data staged")
            continue
        
        # Get column info
        cur.execute(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = '{table}'
            ORDER BY ordinal_position
            LIMIT 10
        """)
        columns = cur.fetchall()
        
        print(f"\nColumns ({len(columns)} shown):")
        for col_name, col_type in columns[:10]:
            print(f"  - {col_name}: {col_type}")
        
        # Get date range if date columns exist
        date_columns = []
        for col_name, col_type in columns:
            if 'date' in col_name.lower() or 'timestamp' in col_type.lower():
                date_columns.append(col_name)
        
        if date_columns:
            date_col = date_columns[0]
            try:
                cur.execute(f"SELECT MIN({date_col}), MAX({date_col}) FROM {table}")
                min_date, max_date = cur.fetchone()
                if min_date and max_date:
                    print(f"\nDate Range ({date_col}):")
                    print(f"  Earliest: {min_date}")
                    print(f"  Latest: {max_date}")
            except Exception as e:
                pass
        
        # Sample first few records
        print(f"\nSample Records (first 3):")
        cur.execute(f"SELECT * FROM {table} LIMIT 3")
        sample = cur.fetchall()
        
        for i, row in enumerate(sample, 1):
            print(f"\n  Record {i}:")
            for col_idx, (col_name, _) in enumerate(columns):
                if col_idx < len(row):
                    value = row[col_idx]
                    if value is not None:
                        # Truncate long values
                        val_str = str(value)
                        if len(val_str) > 50:
                            val_str = val_str[:50] + "..."
                        print(f"    {col_name}: {val_str}")
    
    # Summary
    print(f"\n{'='*80}")
    print("STAGING SUMMARY")
    print('='*80)
    print()
    
    total_staged = 0
    tables_with_data = []
    tables_empty = []
    
    for table in staging_tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        total_staged += count
        
        if count > 0:
            tables_with_data.append((table, count))
        else:
            tables_empty.append(table)
    
    print(f"Total Staging Tables: {len(staging_tables)}")
    print(f"Tables with Data: {len(tables_with_data)}")
    print(f"Empty Tables: {len(tables_empty)}")
    print(f"Total Records Staged: {total_staged:,}")
    print()
    
    if tables_with_data:
        print("Tables with Staged Data:")
        for table, count in tables_with_data:
            print(f"  ✓ {table}: {count:,} records")
    
    if tables_empty:
        print("\nEmpty Staging Tables:")
        for table in tables_empty:
            print(f"  ○ {table}")
    
    print()
    print("=" * 80)
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_staging_status()
