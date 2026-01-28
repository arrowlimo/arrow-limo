#!/usr/bin/env python3
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Neon connection
NEON_HOST = os.environ.get("NEON_HOST", "ep-raspy-river-a5nrq7tq-pooler.us-east-1.neon.tech")
NEON_USER = os.environ.get("NEON_USER", "colocated_user")
NEON_PASSWORD = os.environ.get("NEON_PASSWORD", "SplitRobust2025!")
NEON_DB = os.environ.get("NEON_DB", "almsdata")

try:
    neon_conn = psycopg2.connect(
        host=NEON_HOST,
        user=NEON_USER,
        password=NEON_PASSWORD,
        database=NEON_DB,
        sslmode="require"
    )
    neon_cur = neon_conn.cursor(cursor_factory=RealDictCursor)
    
    print("=== Checking banking_transactions on Neon ===")
    
    # Check if table exists
    neon_cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'banking_transactions'
        )
    """)
    exists = neon_cur.fetchone()[0]
    print(f"Table exists: {exists}")
    
    if exists:
        # Check schema
        neon_cur.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'banking_transactions'
            ORDER BY ordinal_position
            LIMIT 5
        """)
        print(f"\nFirst 5 columns:")
        for row in neon_cur.fetchall():
            print(f"  {row['column_name']}: {row['data_type']} (nullable: {row['is_nullable']})")
        
        # Check row count
        neon_cur.execute("SELECT COUNT(*) FROM banking_transactions")
        count = neon_cur.fetchone()[0]
        print(f"\nTotal rows: {count}")
        
        # Check if it's empty or has data
        if count > 0:
            neon_cur.execute("""
                SELECT transaction_id, mapped_bank_account_id, transaction_date, description, amount
                FROM banking_transactions 
                LIMIT 3
            """)
            print(f"\nSample rows:")
            for row in neon_cur.fetchall():
                print(f"  {row}")
        else:
            print("\nTable is empty - no rows found")
    
    neon_cur.close()
    neon_conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
