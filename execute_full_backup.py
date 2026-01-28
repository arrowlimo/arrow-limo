"""Create full database backup using pg_dump or Python fallback."""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

backup_dir = Path("L:\\limo\\database_backups")
backup_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_file = backup_dir / f"almsdata_full_dump_{timestamp}.sql"

print("=" * 80)
print("FULL DATABASE BACKUP")
print("=" * 80)
print(f"Backup file: {backup_file}")
print()

# Try pg_dump first
try:
    print("Attempting pg_dump...")
    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASSWORD
    
    result = subprocess.run(
        ["pg_dump", "-h", DB_HOST, "-U", DB_USER, "-d", DB_NAME, "-F", "p"],
        capture_output=True,
        text=True,
        env=env,
        timeout=300
    )
    
    if result.returncode == 0:
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(result.stdout)
        
        size_mb = backup_file.stat().st_size / (1024 * 1024)
        print(f"✅ pg_dump succeeded: {size_mb:.2f} MB")
        print(f"   File: {backup_file}")
    else:
        print(f"⚠️ pg_dump failed: {result.stderr}")
        raise Exception("pg_dump error")

except FileNotFoundError:
    print("⚠️ pg_dump not found. Using Python fallback (data + schema only)...")
    
    import psycopg2
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write("-- Arrow Limousine Full Database Backup (Python Fallback)\n")
        f.write(f"-- Created: {datetime.now().isoformat()}\n")
        f.write(f"-- Database: {DB_NAME}\n\n")
        
        # Get all tables
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
        tables = [r[0] for r in cur.fetchall()]
        
        f.write(f"-- Total tables: {len(tables)}\n\n")
        
        # Dump each table schema + data
        for table in tables:
            try:
                # Get CREATE TABLE statement
                cur.execute(f"""
                    SELECT pg_get_tabledef('{table}'::regclass)
                """)
                create_stmt = cur.fetchone()[0]
                if create_stmt:
                    f.write(f"\n{create_stmt};\n\n")
                
                # Get row count
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cur.fetchone()[0]
                
                if row_count > 0:
                    # Export data as COPY
                    f.write(f"COPY {table} FROM stdin;\n")
                    cur.execute(f"SELECT * FROM {table}")
                    for row in cur.fetchall():
                        f.write("\t".join(str(v) if v is not None else "\\N" for v in row) + "\n")
                    f.write("\\.\n\n")
                
                print(f"  Dumped {table}: {row_count:,} rows")
            
            except Exception as e:
                print(f"  ⚠️ Error dumping {table}: {e}")
    
    cur.close()
    conn.close()
    
    size_mb = backup_file.stat().st_size / (1024 * 1024)
    print(f"\n✅ Python fallback complete: {size_mb:.2f} MB")
    print(f"   File: {backup_file}")

print("\n" + "=" * 80)
print("✅ BACKUP COMPLETE")
print("=" * 80)
