#!/usr/bin/env python3
"""
Mark all clients with comma-separated company_name as individuals (corporate_parent_id=0)
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
    print("DRY RUN: Corporate names with commas")
    print("=" * 80)
    cur.execute("""
        SELECT COUNT(*) as count_with_comma
        FROM clients
        WHERE company_name LIKE '%,%'
          AND corporate_parent_id != 0;
    """)
    
    count = cur.fetchone()[0]
    print(f"Clients with comma in company_name (currently not marked as individuals): {count}\n")
    
    # Show sample
    print("Sample records to be updated:")
    cur.execute("""
        SELECT 
            client_id,
            client_name,
            company_name,
            corporate_parent_id,
            corporate_role
        FROM clients
        WHERE company_name LIKE '%,%'
          AND corporate_parent_id != 0
        LIMIT 15;
    """)
    
    for row in cur.fetchall():
        client_id, client_name, company_name, parent_id, role = row
        print(f"  ID {client_id}: {client_name:30} | company='{company_name}' | parent={parent_id} | role={role}")
    
    # Step 2: Ask for confirmation
    print("\n" + "=" * 80)
    response = input("Mark all these as individuals (corporate_parent_id=0)? [y/N]: ").strip().lower()
    
    if response == 'y':
        print("🔄 Updating...")
        cur.execute("""
            UPDATE clients
            SET corporate_parent_id = 0,
                corporate_role = NULL
            WHERE company_name LIKE '%,%'
              AND corporate_parent_id != 0;
        """)
        
        conn.commit()
        print(f"✅ Updated {cur.rowcount} rows to corporate_parent_id=0")
    else:
        print("❌ Cancelled")
        conn.rollback()
    
    # Step 3: Final verification
    print("\n" + "=" * 80)
    print("VERIFICATION: Current state")
    print("=" * 80)
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE corporate_parent_id = 0) as individuals,
            COUNT(*) FILTER (WHERE corporate_parent_id > 0) as corporate_employees,
            COUNT(*) as total
        FROM clients;
    """)
    
    individuals, employees, total = cur.fetchone()
    print(f"Individuals (corporate_parent_id=0):  {individuals}")
    print(f"Corporate employees (>0):             {employees}")
    print(f"Total:                                {total}")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    if conn:
        conn.rollback()
        conn.close()
    exit(1)
