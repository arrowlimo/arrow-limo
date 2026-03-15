# Sync Neon to Local using Python (matches app connection method)
import psycopg2
import os
from datetime import datetime

print("=== Neon to Local Database Sync (Python) ===\n")

# Neon credentials
neon_config = {
    'host': 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
    'port': 5432,
    'database': 'neondb',
    'user': 'neondb_owner',
    'password': 'npg_rlL0yK9pvfCW',
    'sslmode': 'require'
}

# Local credentials  
local_config = {
    'host': 'localhost',
    'port': 5432,
    'database': 'almsdata',
    'user': 'postgres',
    'password': 'ArrowLimousine'
}

try:
    print("Step 1: Testing Neon connection...")
    neon_conn = psycopg2.connect(**neon_config)
    print("✓ Neon connection successful\n")
    
    # Get table list
    with neon_conn.cursor() as cur:
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]
    
    print(f"Found {len(tables)} tables in Neon")
    neon_conn.close()
    
    # Create dump file path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dump_file = f"L:/limo/neon_python_dump_{timestamp}.sql"
    
    print(f"\nStep 2: Dumping Neon using pg_dump...")
    os.environ['PGPASSWORD'] = neon_config['password']
    cmd = f'pg_dump -h {neon_config["host"]} -p {neon_config["port"]} -U {neon_config["user"]} -d {neon_config["database"]} --no-owner --no-privileges -f "{dump_file}"'
    result = os.system(cmd)
    del os.environ['PGPASSWORD']
    
    if result != 0:
        print(f"✗ pg_dump failed (exit code {result})")
        print("\nAlternative: Export from Neon console manually")
        exit(1)
    
    print(f"✓ Dump created: {dump_file}\n")
    
    print("Step 3: Restoring to local database...")
    os.environ['PGPASSWORD'] = local_config['password']
    
    # Drop and recreate database
    os.system(f'psql -h {local_config["host"]} -U {local_config["user"]} -d postgres -c "DROP DATABASE IF EXISTS {local_config["database"]};"')
    os.system(f'psql -h {local_config["host"]} -U {local_config["user"]} -d postgres -c "CREATE DATABASE {local_config["database"]};"')
    
    # Restore dump
    cmd = f'psql -h {local_config["host"]} -U {local_config["user"]} -d {local_config["database"]} -f "{dump_file}"'
    result = os.system(cmd)
    del os.environ['PGPASSWORD']
    
    if result != 0:
        print(f"✗ Restore failed (exit code {result})")
        exit(1)
    
    print("✓ Restore complete\n")
    
    print("Step 4: Verifying local database...")
    local_conn = psycopg2.connect(**local_config)
    with local_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';")
        table_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM receipts;")
        receipt_count = cur.fetchone()[0]
        
        # Check for invoice_number column
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'receipts' AND column_name = 'invoice_number'
        """)
        has_invoice = cur.fetchone() is not None
    
    local_conn.close()
    
    print(f"✓ Tables: {table_count}")
    print(f"✓ Receipts: {receipt_count}")
    print(f"✓ invoice_number column: {'YES' if has_invoice else 'NO'}")
    print("\n=== Sync Complete ===")
    print(f"Dump file: {dump_file}")
    
except psycopg2.Error as e:
    print(f"✗ Database error: {e}")
    exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    exit(1)
