"""
Export Complete Arrow Limousine Data Ecosystem to JSON - SIMPLE VERSION
=======================================================================

Creates a comprehensive JSON export of the entire almsdata database with ALL
table data without making schema assumptions. This is the "export everything" approach.

Usage:
    python scripts/export_complete_almsdata_simple.py
    
    # With compression
    python scripts/export_complete_almsdata_simple.py --compress
    
    # Limit rows for testing
    python scripts/export_complete_almsdata_simple.py --limit 1000
"""

import os
import json
import argparse
from datetime import datetime, date, time
from decimal import Decimal
import gzip
import psycopg2

def get_db_connection():
    """Get PostgreSQL database connection"""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def json_serial(obj):
    """JSON serializer for objects not serializable by default"""
    if obj is None:
        return None
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

def get_table_list(cur):
    """Get all tables excluding staging tables"""
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        AND table_name NOT LIKE 'staging_%'
        AND table_name NOT LIKE '%_staging'
        AND table_name NOT LIKE '%backup%'
        AND table_name NOT LIKE '%_ARCHIVED_%'
        ORDER BY table_name
    """)
    return [row[0] for row in cur.fetchall()]

def get_table_schema(cur, table_name):
    """Get column definitions for a table"""
    cur.execute("""
        SELECT 
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns 
        WHERE table_name = %s 
        ORDER BY ordinal_position
    """, (table_name,))
    
    schema = []
    for row in cur.fetchall():
        schema.append({
            "name": row[0],
            "type": row[1],
            "max_length": row[2],
            "nullable": row[3] == 'YES',
            "default": row[4]
        })
    return schema

def get_table_stats(cur, table_name):
    """Get basic statistics about a table"""
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cur.fetchone()[0]
        
        # Try to find a date column
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s 
            AND data_type IN ('date', 'timestamp', 'timestamp without time zone')
            ORDER BY ordinal_position
            LIMIT 1
        """, (table_name,))
        
        date_col = cur.fetchone()
        date_range = None
        
        if date_col:
            date_col_name = date_col[0]
            try:
                cur.execute(f"""
                    SELECT 
                        MIN({date_col_name})::text,
                        MAX({date_col_name})::text
                    FROM {table_name}
                    WHERE {date_col_name} IS NOT NULL
                """)
                result = cur.fetchone()
                if result and result[0]:
                    date_range = {"min": result[0], "max": result[1], "column": date_col_name}
            except:
                pass
        
        return {
            "row_count": row_count,
            "date_range": date_range
        }
    except Exception as e:
        return {"error": str(e)}

def get_table_data(cur, table_name, limit=None):
    """Get all data from a table"""
    try:
        limit_clause = f"LIMIT {limit}" if limit else ""
        cur.execute(f"SELECT * FROM {table_name} {limit_clause}")
        
        columns = [desc[0] for desc in cur.description]
        rows = []
        
        for row in cur.fetchall():
            row_dict = {}
            for i, col in enumerate(columns):
                row_dict[col] = row[i]
            rows.append(row_dict)
        
        return rows, columns
    except Exception as e:
        return None, str(e)

def main():
    parser = argparse.ArgumentParser(description='Export complete almsdata to JSON (simple version)')
    parser.add_argument('--output', default='reports/complete_almsdata_export.json',
                       help='Output JSON file path')
    parser.add_argument('--compress', action='store_true',
                       help='Compress output with gzip')
    parser.add_argument('--limit', type=int,
                       help='Limit rows per table (for testing)')
    args = parser.parse_args()
    
    print("=" * 80)
    print("ARROW LIMOUSINE COMPLETE DATA EXPORT (SIMPLE VERSION)")
    print("=" * 80)
    print()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Initialize export structure
    export_data = {
        "metadata": {
            "export_date": datetime.now().isoformat(),
            "database": "almsdata",
            "version": "1.0-simple",
            "description": "Complete Arrow Limousine data export - all tables, all rows",
            "row_limit_per_table": args.limit if args.limit else "none"
        },
        "tables": {}
    }
    
    # Get table list
    print("Discovering tables...")
    conn.rollback()  # Clear any transaction state
    tables = get_table_list(cur)
    export_data["metadata"]["total_tables"] = len(tables)
    print(f"Found {len(tables)} tables (excluding staging tables)")
    print()
    
    # Export all tables
    print("Exporting complete table data...")
    print("-" * 80)
    
    total_rows = 0
    successful_tables = 0
    failed_tables = 0
    
    for i, table_name in enumerate(tables, 1):
        try:
            conn.rollback()  # Clear any errors before each table
            print(f"[{i}/{len(tables)}] {table_name}...", end=" ", flush=True)
            
            stats = get_table_stats(cur, table_name)
            schema = get_table_schema(cur, table_name)
            rows, columns = get_table_data(cur, table_name, limit=args.limit)
            
            if rows is None:
                # Error occurred
                print(f"✗ Error: {columns}")
                failed_tables += 1
                export_data["tables"][table_name] = {
                    "error": columns,
                    "schema": schema,
                    "stats": stats
                }
            else:
                row_count = stats.get("row_count", len(rows))
                total_rows += row_count
                successful_tables += 1
                
                export_data["tables"][table_name] = {
                    "schema": schema,
                    "row_count": row_count,
                    "date_range": stats.get("date_range"),
                    "columns": columns,
                    "rows": rows
                }
                
                print(f"✓ {row_count:,} rows")
            
        except Exception as e:
            print(f"✗ Exception: {e}")
            failed_tables += 1
            conn.rollback()
            export_data["tables"][table_name] = {
                "error": str(e)
            }
    
    export_data["metadata"]["total_rows"] = total_rows
    export_data["metadata"]["successful_tables"] = successful_tables
    export_data["metadata"]["failed_tables"] = failed_tables
    
    cur.close()
    conn.close()
    
    # Write output
    print()
    print("=" * 80)
    print("Writing export file...")
    
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    if args.compress:
        output_file = args.output + '.gz'
        with gzip.open(output_file, 'wt', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=json_serial)
    else:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=json_serial)
    
    file_size = os.path.getsize(output_file if args.compress else args.output)
    file_size_mb = file_size / (1024 * 1024)
    
    print(f"✓ Export complete: {args.output}")
    if args.compress:
        print(f"  Compressed file: {output_file}")
    print(f"  File size: {file_size_mb:.1f} MB")
    print(f"  Total tables: {len(tables)}")
    print(f"  Successful: {successful_tables}")
    print(f"  Failed: {failed_tables}")
    print(f"  Total rows: {total_rows:,}")
    print()
    print("=" * 80)

if __name__ == "__main__":
    main()
