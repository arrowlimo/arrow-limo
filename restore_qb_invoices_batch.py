#!/usr/bin/env python3
"""
Restore qb_export_invoices from Neon to local (with conflict handling)
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
    # Connect to Neon and get schema
    neon_conn = psycopg2.connect(**NEON_CONN)
    neon_cur = neon_conn.cursor()
    
    # Get column info
    neon_cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'qb_export_invoices'
        ORDER BY ordinal_position
    """)
    
    columns = neon_cur.fetchall()
    col_names = [c[0] for c in columns]
    print(f"✅ Found qb_export_invoices in Neon with {len(columns)} columns")
    
    # Fetch all data using quoted column names
    quoted_cols = ', '.join([f'"{col}"' for col in col_names])
    neon_cur.execute(f"SELECT {quoted_cols} FROM qb_export_invoices")
    rows = neon_cur.fetchall()
    print(f"✅ Fetched {len(rows)} rows from Neon\n")
    
    neon_cur.close()
    neon_conn.close()
    
    # Connect to local
    local_conn = psycopg2.connect(**LOCAL_CONN)
    local_cur = local_conn.cursor()
    
    # Drop if exists
    local_cur.execute("DROP TABLE IF EXISTS qb_export_invoices CASCADE")
    
    # Build CREATE TABLE with quoted column names and proper types
    col_defs = []
    pk_col = None
    for col_name, col_type, is_nullable in columns:
        if "Invoice" in col_name:
            pk_col = col_name  # Invoice # is the natural PK
        
        if col_type == "integer":
            type_str = "INT"
        elif col_type.startswith("numeric"):
            type_str = "DECIMAL(15,2)"
        elif col_type == "date":
            type_str = "DATE"
        elif col_type.startswith("timestamp"):
            type_str = "TIMESTAMPTZ"
        elif col_type == "text":
            type_str = "TEXT"
        else:
            type_str = col_type
        
        col_defs.append(f'"{col_name}" {type_str}')
    
    # Add PK constraint
    create_stmt = f"""
    CREATE TABLE qb_export_invoices (
        {', '.join(col_defs)},
        PRIMARY KEY ("{pk_col}")
    )
    """
    
    print("Creating table in local...")
    local_cur.execute(create_stmt)
    local_conn.commit()
    
    # Build insert statement with batch size
    quoted_col_names = ', '.join([f'"{col}"' for col in col_names])
    placeholders = ', '.join(['%s'] * len(col_names))
    insert_stmt = f"INSERT INTO qb_export_invoices ({quoted_col_names}) VALUES ({placeholders})"
    
    print(f"Inserting {len(rows)} rows in batches...")
    batch_size = 1000
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        try:
            local_cur.executemany(insert_stmt, batch)
            local_conn.commit()
            print(f"  ✓ Inserted {min(i+batch_size, len(rows))}/{len(rows)} rows")
        except psycopg2.IntegrityError as e:
            print(f"  ⚠️  Batch {i//batch_size}: Integrity error (likely duplicate) - continuing...")
            local_conn.rollback()
            # Try one-by-one to skip duplicates
            for row in batch:
                try:
                    local_cur.execute(insert_stmt, row)
                    local_conn.commit()
                except psycopg2.IntegrityError:
                    local_conn.rollback()
    
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
