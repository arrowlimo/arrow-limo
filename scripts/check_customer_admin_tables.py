#!/usr/bin/env python3
"""
Check Customer Admin Table and Compare with Clients
==================================================

Finds customer admin table and compares names with almsdata.clients
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

PG_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '')
}

def main():
    print('🔍 SEARCHING FOR CUSTOMER ADMIN TABLES')
    print('=' * 50)

    with psycopg2.connect(**PG_CONFIG) as conn:
        with conn.cursor() as cur:
            # Find tables with 'customer' or 'admin' in name
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND (table_name ILIKE '%customer%' OR table_name ILIKE '%admin%')
                ORDER BY table_name
            """)
            
            admin_tables = cur.fetchall()
            if admin_tables:
                print('Found tables with customer/admin:')
                for table in admin_tables:
                    table_name = table[0]
                    print(f'\n📋 {table_name}')
                    
                    # Get record count
                    try:
                        cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                        count = cur.fetchone()[0]
                        print(f'   {count:,} records')
                        
                        # Get column info
                        cur.execute(f"""
                            SELECT column_name, data_type 
                            FROM information_schema.columns 
                            WHERE table_name = '{table_name}' 
                            ORDER BY ordinal_position
                        """)
                        columns = cur.fetchall()
                        print(f'   Columns: {[col[0] for col in columns]}')
                        
                        # Show sample data if it exists
                        if count > 0:
                            cur.execute(f'SELECT * FROM "{table_name}" LIMIT 3')
                            samples = cur.fetchall()
                            if samples:
                                print(f'   Sample data:')
                                for i, sample in enumerate(samples):
                                    print(f'     Row {i+1}: {sample}')
                                    
                    except Exception as e:
                        print(f'   ERROR: {e}')
            else:
                print('No tables found with customer/admin in name')
                
            # Also check all tables that might contain names
            print('\n🔍 TABLES THAT MIGHT CONTAIN CLIENT NAMES:')
            name_related_tables = ['clients', 'customer_name_mapping', 'limo_clients', 'limo_clients_clean']
            
            for table_name in name_related_tables:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cur.fetchone()[0]
                    if count > 0:
                        print(f'\n📋 {table_name} ({count:,} records)')
                        
                        # Get columns that might contain names
                        cur.execute(f"""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = '{table_name}' 
                            AND (column_name ILIKE '%name%' OR column_name ILIKE '%client%')
                            ORDER BY ordinal_position
                        """)
                        name_columns = [col[0] for col in cur.fetchall()]
                        
                        if name_columns:
                            print(f'   Name columns: {name_columns}')
                            
                            # Show some sample names
                            for col in name_columns[:2]:  # Limit to first 2 columns
                                try:
                                    cur.execute(f'SELECT DISTINCT {col} FROM {table_name} WHERE {col} IS NOT NULL LIMIT 5')
                                    names = [row[0] for row in cur.fetchall()]
                                    if names:
                                        print(f'   Sample {col}: {names}')
                                except:
                                    pass
                                    
                except Exception as e:
                    print(f'   {table_name}: {e}')

if __name__ == "__main__":
    main()