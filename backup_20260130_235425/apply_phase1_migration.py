#!/usr/bin/env python3
"""
Apply Phase 1 Data Quality Fixes via Python
Executes the SQL migration using psycopg2
"""

import os
import psycopg2
from pathlib import Path
from datetime import datetime

# Database Configuration
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def apply_migration():
    """Apply Phase 1 data quality fixes"""
    
    print("=" * 80)
    print("APPLYING PHASE 1 DATA QUALITY FIXES")
    print("=" * 80)
    print(f"Started: {datetime.now()}\n")
    
    # Read SQL file
    sql_file = Path("l:/limo/migrations/20260123_phase1_data_quality_fixes.sql")
    
    if not sql_file.exists():
        print(f"❌ SQL file not found: {sql_file}")
        return False
    
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    # Connect to database
    print("📊 Connecting to database...")
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    conn.autocommit = False
    cur = conn.cursor()
    
    try:
        print("📊 Executing migration SQL...\n")
        
        # Execute SQL
        cur.execute(sql)
        
        # Fetch verification results if any
        try:
            while True:
                if cur.description:
                    results = cur.fetchall()
                    if results:
                        print("\n📊 Verification Results:")
                        for row in results:
                            print(f"   {row}")
                if not cur.nextset():
                    break
        except:
            pass
        
        # Commit transaction
        print("\n📊 Committing changes...")
        conn.commit()
        
        print("\n✅ Migration applied successfully!")
        print(f"\nCompleted: {datetime.now()}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error applying migration: {e}")
        print("📊 Rolling back changes...")
        conn.rollback()
        return False
        
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    success = apply_migration()
    exit(0 if success else 1)
