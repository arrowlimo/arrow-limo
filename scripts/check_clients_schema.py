#!/usr/bin/env python3
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

with psycopg2.connect(**PG_CONFIG) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'clients' 
            ORDER BY ordinal_position
        """)
        
        columns = cur.fetchall()
        print('📋 CLIENTS TABLE SCHEMA:')
        for col in columns:
            print(f'   {col[0]:<25} {col[1]:<20} {col[2]}')