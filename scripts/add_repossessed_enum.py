#!/usr/bin/env python3
"""
Add repossessed/stolen asset status to asset tracking system
"""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


def main():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    try:
        # Add repossessed to asset_ownership_type enum
        cur.execute("""
            ALTER TYPE asset_ownership_type ADD VALUE 'repossessed' BEFORE 'rental'
        """)
        
        # Add stolen to asset_status enum
        cur.execute("""
            ALTER TYPE asset_status ADD VALUE 'stolen' AFTER 'repossessed'
        """)
        
        conn.commit()
        print("✅ Added repossessed/stolen statuses to asset enums")
        
    except psycopg2.errors.DuplicateObject:
        print("⚠️  Enum values already exist")
        conn.rollback()
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
