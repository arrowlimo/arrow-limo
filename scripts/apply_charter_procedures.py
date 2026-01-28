#!/usr/bin/env python3
"""
Apply Charter Management Procedures to Database
Creates lock, unlock, cancel, and delete functions in PostgreSQL
"""

import os
import psycopg2
from pathlib import Path

# Database connection
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = int(os.environ.get('DB_PORT', 5432))
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

def apply_procedures():
    """Apply procedures to database"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()
        
        print("📋 Reading procedure definitions...")
        
        # Read the SQL file
        sql_file = Path(__file__).parent.parent / 'scripts' / 'charter_management_procedures.sql'
        
        if not sql_file.exists():
            print(f"❌ SQL file not found: {sql_file}")
            return False
        
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        print("⚙️  Executing procedures...")
        
        # Execute the SQL
        cur.execute(sql_content)
        conn.commit()
        
        print("✅ Charter management procedures created successfully!")
        print("\nCreated functions:")
        print("  • lock_charter(reserve_number)")
        print("  • unlock_charter(reserve_number)")
        print("  • cancel_charter(reserve_number)")
        print("  • delete_charge(reserve_number, charge_id, reason)")
        print("  • get_charter_lock_status(reserve_number)")
        print("  • get_charter_balance(reserve_number)")
        print("  • record_nfd_charge(reserve_number)")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error applying procedures: {str(e)}")
        return False

if __name__ == "__main__":
    success = apply_procedures()
    exit(0 if success else 1)
