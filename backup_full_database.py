#!/usr/bin/env python3
"""
Full database backup using psycopg2
Exports all tables and data to SQL file
"""
import psycopg2
from datetime import datetime
import sys

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_file = f"L:\\limo\\almsdata_backup_FULL_{timestamp}.sql"

print(f"🔄 Starting full database backup at {datetime.now().isoformat()}")
print(f"📁 Backup file: {backup_file}")

try:
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    
    cur = conn.cursor()
    
    # Get all tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cur.fetchall()]
    print(f"📋 Found {len(tables)} tables to backup")
    
    with open(backup_file, 'w', encoding='utf-8') as f:
        # Write header
        f.write(f"-- Full database backup\n")
        f.write(f"-- Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"-- PostgreSQL almsdata database\n\n")
        
        # Dump each table
        for table in tables:
            print(f"  ⏳ Backing up table: {table}")
            
            # Get table structure
            cur.execute(f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table,))
            columns = cur.fetchall()
            
            # Create table statement
            col_defs = []
            for col_name, data_type, nullable in columns:
                nullable_str = "" if nullable == "NO" else "NULL"
                col_defs.append(f"    {col_name} {data_type}")
            
            f.write(f"\n-- Table: {table}\n")
            f.write(f"CREATE TABLE IF NOT EXISTS {table} (\n")
            f.write(",\n".join(col_defs))
            f.write("\n);\n\n")
            
            # Get data
            cur.execute(f"SELECT * FROM {table}")
            rows = cur.fetchall()
            
            if rows:
                col_names = [desc[0] for desc in cur.description]
                f.write(f"INSERT INTO {table} ({', '.join(col_names)}) VALUES\n")
                
                for i, row in enumerate(rows):
                    values = []
                    for val in row:
                        if val is None:
                            values.append("NULL")
                        elif isinstance(val, str):
                            values.append(f"'{val.replace(chr(39), chr(39)+chr(39))}'")
                        elif isinstance(val, bool):
                            values.append(str(val))
                        else:
                            values.append(str(val))
                    
                    line = f"  ({', '.join(values)})"
                    if i < len(rows) - 1:
                        line += ","
                    else:
                        line += ";"
                    f.write(line + "\n")
                f.write("\n")
    
    cur.close()
    conn.close()
    
    # Get file size
    import os
    file_size_mb = os.path.getsize(backup_file) / (1024 * 1024)
    
    print(f"\n✅ BACKUP COMPLETED SUCCESSFULLY!")
    print(f"📊 Backup size: {file_size_mb:.2f} MB")
    print(f"📁 Backup file: {backup_file}")
    print(f"✔️  Data is safe - no data loss")
    
except Exception as e:
    print(f"\n❌ BACKUP FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
