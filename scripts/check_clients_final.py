#!/usr/bin/env python3
"""
Check if Client Names are in almsdata.clients
============================================
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
    print('🔍 CHECKING CLIENT NAMES IN ALMSDATA.CLIENTS')
    print('=' * 50)

    with psycopg2.connect(**PG_CONFIG) as conn:
        with conn.cursor() as cur:
            # Check the specific high-value customers we were trying to fix
            high_value_customers = [
                'Waste Connections of Canada',
                'NOVA Chemicals Corporation', 
                'ME Global',
                'Bredin Centre for Learning',
                'carrier enterprise',
                'N/a'
            ]
            
            print('💰 HIGH-VALUE CUSTOMERS CHECK:')
            found_count = 0
            for company in high_value_customers:
                cur.execute("""
                    SELECT client_id, account_number, company_name, client_name, email
                    FROM clients 
                    WHERE company_name ILIKE %s
                """, (f'%{company}%',))
                
                result = cur.fetchone()
                if result:
                    client_id, account, company_name, client_name, email = result
                    print(f'   [OK] {company}')
                    print(f'       ID: {client_id} | Account: {account} | Name: {client_name}')
                    if email:
                        print(f'       Email: {email}')
                    found_count += 1
                else:
                    print(f'   [FAIL] {company} - NOT FOUND')
            
            # Check the LMS missing customers
            lms_missing = ['Knust', 'Marshall', 'Brown', 'Maurier', 'Lecers']
            print(f'\n📋 LMS MISSING CUSTOMERS CHECK:')
            lms_found = 0
            for company in lms_missing:
                cur.execute("""
                    SELECT client_id, account_number, company_name
                    FROM clients 
                    WHERE company_name ILIKE %s
                """, (f'%{company}%',))
                
                result = cur.fetchone()
                if result:
                    client_id, account, company_name = result
                    print(f'   [OK] {company} - ID: {client_id}, Account: {account}')
                    lms_found += 1
                else:
                    print(f'   [FAIL] {company} - NOT FOUND')
            
            # Show newest clients added
            print(f'\n🆕 NEWEST CLIENTS ADDED:')
            cur.execute("""
                SELECT client_id, account_number, company_name, client_name, created_at
                FROM clients 
                ORDER BY client_id DESC
                LIMIT 10
            """)
            
            newest = cur.fetchall()
            for client in newest:
                client_id, account, company, name, created = client
                print(f'   {client_id}: {account} - {company} ({name}) | {created.strftime("%Y-%m-%d %H:%M")}')
            
            # Show total count and recent additions
            cur.execute('SELECT COUNT(*) FROM clients')
            total_count = cur.fetchone()[0]
            
            cur.execute("""
                SELECT COUNT(*) FROM clients 
                WHERE created_at >= CURRENT_DATE
            """)
            todays_additions = cur.fetchone()[0]
            
            print(f'\n📊 SUMMARY:')
            print(f'   • Total clients: {total_count:,}')
            print(f'   • Added today: {todays_additions}')
            print(f'   • High-value customers found: {found_count}/{len(high_value_customers)}')
            print(f'   • LMS customers found: {lms_found}/{len(lms_missing)}')

if __name__ == "__main__":
    main()