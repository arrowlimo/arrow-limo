#!/usr/bin/env python3
"""
Mark all remaining clients as corporate_parent_id=1 (placeholder for manual fixup)
"""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Step 1: Dry run - count affected rows
    print("=" * 80)
    print("DRY RUN: All remaining clients → corporate_parent_id=1")
    print("=" * 80)
    cur.execute("""
        SELECT COUNT(*) as count
        FROM clients
        WHERE corporate_parent_id = 0;
    """)
    
    count = cur.fetchone()[0]
    print(f"Clients currently with corporate_parent_id=0: {count}\n")
    
    # Show sample
    print("Sample records to be updated to corporate_parent_id=1:")
    cur.execute("""
        SELECT 
            client_id,
            client_name,
            company_name,
            corporate_parent_id
        FROM clients
        WHERE corporate_parent_id = 0
        LIMIT 20;
    """)
    
    for row in cur.fetchall():
        client_id, client_name, company_name, parent_id = row
        print(f"  ID {client_id}: {client_name:30} | company='{company_name}'")
    
    # Step 2: Ask for confirmation
    print("\n" + "=" * 80)
    response = input(f"Mark all {count} records as corporate_parent_id=1? [y/N]: ").strip().lower()
    
    if response == 'y':
        print("🔄 Updating...")
        cur.execute("""
            UPDATE clients
            SET corporate_parent_id = 1
            WHERE corporate_parent_id = 0;
        """)
        
        conn.commit()
        print(f"✅ Updated {cur.rowcount} rows to corporate_parent_id=1")
    else:
        print("❌ Cancelled")
        conn.rollback()
        conn.close()
        exit(0)
    
    # Step 3: Final verification
    print("\n" + "=" * 80)
    print("VERIFICATION: Current state")
    print("=" * 80)
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE corporate_parent_id = 0) as individuals,
            COUNT(*) FILTER (WHERE corporate_parent_id = 1) as parent_company_1,
            COUNT(*) FILTER (WHERE corporate_parent_id > 1) as other_parents,
            COUNT(*) as total
        FROM clients;
    """)
    
    individuals, parent_1, other, total = cur.fetchone()
    print(f"corporate_parent_id = 0:  {individuals}")
    print(f"corporate_parent_id = 1:  {parent_1}")
    print(f"corporate_parent_id > 1:  {other}")
    print(f"Total:                    {total}")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    if conn:
        conn.rollback()
        conn.close()
    exit(1)
