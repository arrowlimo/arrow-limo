#!/usr/bin/env python
"""
Apply optimistic locking schema migration
Adds version and updated_at columns to key tables
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def apply_migration(conn_params, db_label):
    """Apply migration to a database"""
    print(f"\n{'='*60}")
    print(f"Applying optimistic locking migration to: {db_label}")
    print(f"{'='*60}")
    
    try:
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()
        
        # Tables to add versioning to
        tables = ['charters', 'payments', 'receipts', 'employees', 'vehicles']
        
        for table in tables:
            print(f"\n  Processing table: {table}")
            
            # Add version column
            try:
                cur.execute(f"""
                    ALTER TABLE {table} 
                    ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1
                """)
                print(f"    ✓ Added version column")
            except Exception as e:
                print(f"    ! Version column: {e}")
            
            # Add updated_at column
            try:
                cur.execute(f"""
                    ALTER TABLE {table} 
                    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()
                """)
                print(f"    ✓ Added updated_at column")
            except Exception as e:
                print(f"    ! Updated_at column: {e}")
        
        # Create trigger function
        print(f"\n  Creating trigger function...")
        cur.execute("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        print(f"    ✓ Trigger function created")
        
        # Apply triggers
        print(f"\n  Applying triggers...")
        for table in tables:
            trigger_name = f"update_{table}_updated_at"
            cur.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table}")
            cur.execute(f"""
                CREATE TRIGGER {trigger_name}
                    BEFORE UPDATE ON {table}
                    FOR EACH ROW
                    EXECUTE FUNCTION update_updated_at_column()
            """)
            print(f"    ✓ Trigger on {table}")
        
        # Create indexes
        print(f"\n  Creating indexes...")
        for table in ['charters', 'payments', 'receipts']:
            idx_name = f"idx_{table}_updated_at"
            cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}(updated_at)")
            print(f"    ✓ Index on {table}.updated_at")
        
        conn.commit()
        
        # Verify
        print(f"\n  Verification:")
        for table in tables:
            cur.execute(f"""
                SELECT COUNT(*) AS total,
                       COUNT(version) AS has_version,
                       COUNT(updated_at) AS has_updated_at
                FROM {table}
            """)
            total, has_ver, has_upd = cur.fetchone()
            print(f"    {table:15} {total:6} rows  (version: {has_ver:6}, updated_at: {has_upd:6})")
        
        cur.close()
        conn.close()
        
        print(f"\n✅ Migration completed successfully for {db_label}")
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed for {db_label}: {e}")
        return False


def main():
    """Apply to both local and Neon databases"""
    
    # Local database
    local_params = {
        'host': 'localhost',
        'database': 'almsdata',
        'user': 'postgres',
        'password': '***REDACTED***'
    }
    
    # Neon database
    neon_params = {
        'host': os.getenv('DB_HOST'),
        'database': os.getenv('DB_NAME'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'sslmode': 'require'
    }
    
    # Apply to local
    local_success = apply_migration(local_params, "LOCAL (localhost)")
    
    # Apply to Neon
    neon_success = apply_migration(neon_params, "NEON (remote)")
    
    print(f"\n{'='*60}")
    print(f"MIGRATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Local database:  {'✅ SUCCESS' if local_success else '❌ FAILED'}")
    print(f"  Neon database:   {'✅ SUCCESS' if neon_success else '❌ FAILED'}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
