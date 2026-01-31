#!/usr/bin/env python3
"""
Check Name Column Structure and History
=====================================

Investigates the name column structure in clients table and related tables
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
    print('🔍 CHECKING NAME COLUMN STRUCTURE AND HISTORY')
    print('=' * 60)

    with psycopg2.connect(**PG_CONFIG) as conn:
        with conn.cursor() as cur:
            
            # Check all name-related columns in clients table
            print('📋 NAME-RELATED COLUMNS IN CLIENTS TABLE:')
            cur.execute("""
                SELECT column_name, data_type, is_nullable, character_maximum_length
                FROM information_schema.columns 
                WHERE table_name = 'clients' 
                AND (column_name ILIKE '%name%' OR column_name ILIKE '%first%' OR column_name ILIKE '%last%')
                ORDER BY ordinal_position
            """)
            
            name_columns = cur.fetchall()
            for col in name_columns:
                col_name, data_type, nullable, max_len = col
                len_str = f'({max_len})' if max_len else ''
                print(f'   {col_name:<25} {data_type}{len_str:<15} Nullable: {nullable}')
            
            # Check if there are first_name/last_name columns anywhere
            print(f'\n🔍 SEARCHING FOR FIRST_NAME/LAST_NAME COLUMNS ACROSS ALL TABLES:')
            cur.execute("""
                SELECT table_name, column_name, data_type
                FROM information_schema.columns 
                WHERE table_schema = 'public'
                AND (column_name ILIKE '%first_name%' OR column_name ILIKE '%last_name%' 
                     OR column_name ILIKE '%firstname%' OR column_name ILIKE '%lastname%')
                ORDER BY table_name, column_name
            """)
            
            first_last_columns = cur.fetchall()
            if first_last_columns:
                print('   Found first/last name columns:')
                for table, column, dtype in first_last_columns:
                    print(f'     {table}.{column} ({dtype})')
            else:
                print('   No first_name/last_name columns found')
            
            # Check for fuzzy search related columns/tables
            print(f'\n🔍 SEARCHING FOR FUZZY SEARCH RELATED STRUCTURES:')
            cur.execute("""
                SELECT table_name, column_name, data_type
                FROM information_schema.columns 
                WHERE table_schema = 'public'
                AND (column_name ILIKE '%fuzzy%' OR column_name ILIKE '%search%' 
                     OR column_name ILIKE '%full_name%' OR column_name ILIKE '%name_search%')
                ORDER BY table_name, column_name
            """)
            
            fuzzy_columns = cur.fetchall()
            if fuzzy_columns:
                print('   Found fuzzy/search name columns:')
                for table, column, dtype in fuzzy_columns:
                    print(f'     {table}.{column} ({dtype})')
            else:
                print('   No fuzzy search columns found')
            
            # Sample current name data structure
            print(f'\n📊 CURRENT NAME DATA SAMPLES:')
            cur.execute("""
                SELECT client_id, company_name, client_name
                FROM clients 
                WHERE client_name IS NOT NULL AND client_name != ''
                ORDER BY client_id DESC
                LIMIT 15
            """)
            
            samples = cur.fetchall()
            print('   ID    Company Name                    Client Name')
            print('   ' + '-' * 70)
            for sample in samples:
                client_id, company, client_name = sample
                company_str = (company or 'None')[:25]
                client_str = (client_name or 'None')[:30]
                print(f'   {client_id:<5} {company_str:<30} {client_str}')
            
            # Check LMS and Square for name structure
            print(f'\n📋 NAME STRUCTURE IN RELATED TABLES:')
            
            # LMS customers
            print('   LMS_CUSTOMERS_ENHANCED:')
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns 
                WHERE table_name = 'lms_customers_enhanced'
                AND column_name ILIKE '%name%'
                ORDER BY ordinal_position
            """)
            lms_name_cols = cur.fetchall()
            for col, dtype in lms_name_cols:
                print(f'     {col} ({dtype})')
            
            # Square customers  
            print('   SQUARE_CUSTOMERS:')
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns 
                WHERE table_name = 'square_customers'
                AND column_name ILIKE '%name%'
                ORDER BY ordinal_position
            """)
            square_name_cols = cur.fetchall()
            for col, dtype in square_name_cols:
                print(f'     {col} ({dtype})')
            
            # Check for any migration or history tables
            print(f'\n🕒 CHECKING FOR HISTORICAL NAME STRUCTURE:')
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND (table_name ILIKE '%backup%' OR table_name ILIKE '%history%' 
                     OR table_name ILIKE '%archive%' OR table_name ILIKE '%old%')
                ORDER BY table_name
            """)
            
            history_tables = cur.fetchall()
            if history_tables:
                print('   Found potential history tables:')
                for table in history_tables:
                    print(f'     {table[0]}')
                    
                    # Check if any have first/last name structure
                    try:
                        cur.execute(f"""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = '{table[0]}'
                            AND (column_name ILIKE '%first%' OR column_name ILIKE '%last%')
                        """)
                        old_name_cols = cur.fetchall()
                        if old_name_cols:
                            print(f'       Has first/last: {[col[0] for col in old_name_cols]}')
                    except:
                        pass
            else:
                print('   No history tables found')

if __name__ == "__main__":
    main()