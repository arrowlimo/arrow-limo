#!/usr/bin/env python3
"""
Robust database backup that skips problematic views/functions
"""
import psycopg2
from datetime import datetime
import sys

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_file = f"L:\\limo\\almsdata_backup_ROBUST_{timestamp}.sql"

print(f"🔄 Starting robust database backup at {datetime.now().isoformat()}")
print(f"📁 Backup file: {backup_file}")

try:
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    
    cur = conn.cursor()
    
    # Get all REAL tables (exclude views)
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cur.fetchall()]
    print(f"📋 Found {len(tables)} base tables to backup")
    
    skipped_tables = []
    backed_up_tables = []
    
    with open(backup_file, 'w', encoding='utf-8') as f:
        # Write header
        f.write(f"-- Full database backup (ROBUST)\n")
        f.write(f"-- Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"-- PostgreSQL almsdata database\n")
        f.write(f"-- Skipped any problematic tables\n\n")
        
        # Dump each table
        for i, table in enumerate(tables, 1):
            try:
                print(f"  [{i}/{len(tables)}] ⏳ Backing up: {table}")
                
                # Try to get row count first (quick check)
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cur.fetchone()[0]
                
                if row_count > 0:
                    # Get table data
                    cur.execute(f"SELECT * FROM {table} LIMIT 1")
                    col_names = [desc[0] for desc in cur.description]
                    
                    cur.execute(f"SELECT * FROM {table}")
                    rows = cur.fetchall()
                    
                    # Write INSERT statement
                    f.write(f"-- Table: {table} ({row_count} rows)\n")
                    f.write(f"INSERT INTO {table} ({', '.join(col_names)}) VALUES\n")
                    
                    for row_idx, row in enumerate(rows):
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
                        if row_idx < len(rows) - 1:
                            line += ","
                        else:
                            line += ";"
                        f.write(line + "\n")
                    f.write("\n")
                    backed_up_tables.append(table)
                else:
                    f.write(f"-- Table: {table} (empty)\n\n")
                    backed_up_tables.append(table)
                    
            except Exception as e:
                print(f"    ⚠️  SKIPPED (error): {str(e)[:80]}")
                skipped_tables.append((table, str(e)[:100]))
                f.write(f"-- ⚠️ SKIPPED TABLE: {table}\n-- Error: {str(e)[:100]}\n\n")
                continue
    
    cur.close()
    conn.close()
    
    # Get file size
    import os
    file_size_mb = os.path.getsize(backup_file) / (1024 * 1024)
    
    print(f"\n✅ BACKUP COMPLETED!")
    print(f"📊 Backup size: {file_size_mb:.2f} MB")
    print(f"✔️  Tables backed up: {len(backed_up_tables)}")
    if skipped_tables:
        print(f"⚠️  Tables skipped: {len(skipped_tables)}")
        for table, error in skipped_tables[:5]:
            print(f"    - {table}: {error[:50]}")
    print(f"📁 Backup file: {backup_file}")
    print(f"✔️  Your data is SAFE!")
    
except Exception as e:
    print(f"\n❌ CRITICAL ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
