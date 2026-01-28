#!/usr/bin/env python3
"""
Restore qb_export_invoices table from Neon to local almsdata
"""
import psycopg2

NEON_CONN = {
    'host': 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
    'user': 'neondb_owner',
    'password': '***REMOVED***',
    'database': 'neondb',
    'sslmode': 'require',
}

LOCAL_CONN = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
}

print("Restoring qb_export_invoices from Neon to local...\n")

try:
    # Connect to Neon
    neon_conn = psycopg2.connect(**NEON_CONN)
    neon_cur = neon_conn.cursor()
    
    # Get table schema from Neon
    neon_cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'qb_export_invoices'
        ORDER BY ordinal_position
    """)
    
    columns = neon_cur.fetchall()
    print(f"✅ Found qb_export_invoices in Neon with {len(columns)} columns")
    
    # Fetch all data from Neon
    neon_cur.execute("SELECT * FROM qb_export_invoices ORDER BY id")
    rows = neon_cur.fetchall()
    print(f"✅ Fetched {len(rows)} rows from Neon\n")
    
    neon_cur.close()
    neon_conn.close()
    
    # Connect to local
    local_conn = psycopg2.connect(**LOCAL_CONN)
    local_cur = local_conn.cursor()
    
    # Build CREATE TABLE statement
    col_defs = []
    for col_name, col_type, is_nullable in columns:
        nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
        if col_type == "integer":
            col_defs.append(f"{col_name} INT {nullable}")
        elif col_type.startswith("character varying"):
            col_defs.append(f"{col_name} VARCHAR(255) {nullable}")
        elif col_type.startswith("numeric"):
            col_defs.append(f"{col_name} DECIMAL(15,2) {nullable}")
        elif col_type == "boolean":
            col_defs.append(f"{col_name} BOOLEAN {nullable}")
        elif col_type == "text":
            col_defs.append(f"{col_name} TEXT {nullable}")
        elif col_type.startswith("timestamp"):
            col_defs.append(f"{col_name} TIMESTAMPTZ {nullable}")
        elif col_type == "date":
            col_defs.append(f"{col_name} DATE {nullable}")
        else:
            col_defs.append(f"{col_name} {col_type} {nullable}")
    
    # Find ID column (usually first one)
    id_col = columns[0][0] if columns else "id"
    
    # Create table with PRIMARY KEY on ID
    create_stmt = f"""
    DROP TABLE IF EXISTS qb_export_invoices CASCADE;
    CREATE TABLE qb_export_invoices (
        {', '.join(col_defs[:len(col_defs)-1])},
        {col_defs[-1]},
        PRIMARY KEY ({id_col})
    )
    """
    
    print("Creating table in local...")
    local_cur.execute(create_stmt)
    
    # Insert data
    col_names = ','.join([f'"{col[0]}"' for col in columns])
    placeholders = ','.join(['%s'] * len(columns))
    
    insert_stmt = f"INSERT INTO qb_export_invoices ({col_names}) VALUES ({placeholders})"
    
    print(f"Inserting {len(rows)} rows...")
    local_cur.executemany(insert_stmt, rows)
    
    local_conn.commit()
    
    # Verify
    local_cur.execute("SELECT COUNT(*) FROM qb_export_invoices")
    count = local_cur.fetchone()[0]
    
    print(f"\n✅ Successfully restored qb_export_invoices")
    print(f"   Rows in local: {count}")
    
    local_cur.close()
    local_conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
