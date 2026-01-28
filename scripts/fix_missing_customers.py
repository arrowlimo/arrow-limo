#!/usr/bin/env python3
"""
Fix Missing Customers in Main Clients Table
===========================================

Adds missing high-value customers from Square and LMS systems to main clients table
"""

import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

PG_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '')
}

def main():
    print('🔧 FIXING MISSING CUSTOMERS IN MAIN CLIENTS TABLE')
    print('=' * 60)

    with psycopg2.connect(**PG_CONFIG) as conn:
        with conn.cursor() as cur:
            
            # First, get the highest existing client_id
            cur.execute("SELECT MAX(client_id) FROM clients")
            max_client_id = cur.fetchone()[0] or 0
            next_client_id = max_client_id + 1
            
            print(f'📊 Current max client_id: {max_client_id}')
            print(f'📊 Starting new client_id from: {next_client_id}')
            
            # 1. Fix missing LMS Enhanced customers
            print(f'\n🔍 FIXING MISSING LMS ENHANCED CUSTOMERS:')
            
            lms_missing = [
                ('01021', 'Knust'),
                ('01064', 'Marshall'),
                ('01035', 'Brown'),
                ('01039', 'Maurier'),
                ('01042', 'Lecers')
            ]
            
            lms_added = 0
            for account_no, company_name in lms_missing:
                # Check if already exists (double-check)
                cur.execute("""
                    SELECT client_id FROM clients 
                    WHERE account_number = %s OR company_name ILIKE %s
                """, (account_no, f'%{company_name}%'))
                
                if cur.fetchone():
                    print(f'   [WARN]  {account_no}: {company_name} already exists, skipping')
                    continue
                
                # Insert new client
                cur.execute("""
                    INSERT INTO clients (
                        client_id, account_number, company_name, client_name,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    next_client_id, account_no, company_name, company_name,
                    datetime.now(), datetime.now()
                ))
                
                print(f'   [OK] Added {next_client_id}: {account_no} - {company_name}')
                next_client_id += 1
                lms_added += 1
            
            # 2. Fix missing Square customers (high-value ones)
            print(f'\n💳 FIXING MISSING HIGH-VALUE SQUARE CUSTOMERS:')
            
            # Get the high-value Square customers that are missing
            cur.execute("""
                SELECT first_name, surname, company_name, email_address, 
                       transaction_count, lifetime_spend
                FROM square_customers 
                WHERE company_name IS NOT NULL AND company_name != ''
                AND transaction_count > 0
                ORDER BY CAST(REPLACE(REPLACE(lifetime_spend, '$', ''), ',', '') AS DECIMAL) DESC
            """)
            
            square_customers = cur.fetchall()
            square_added = 0
            
            for row in square_customers:
                first_name, surname, company_name, email, trans_count, lifetime = row
                
                # Check if company already exists in main clients
                cur.execute("""
                    SELECT client_id FROM clients 
                    WHERE company_name ILIKE %s
                """, (f'%{company_name}%',))
                
                if cur.fetchone():
                    continue  # Already exists
                
                # Create account number (next available)
                cur.execute("SELECT MAX(CAST(account_number AS INTEGER)) FROM clients WHERE account_number ~ '^[0-9]+$'")
                max_account = cur.fetchone()[0] or 0
                new_account = str(max_account + 1).zfill(5)
                
                # Insert new client
                full_name = f'{first_name} {surname}'.strip()
                
                cur.execute("""
                    INSERT INTO clients (
                        client_id, account_number, company_name, client_name,
                        email, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    next_client_id, new_account, company_name, full_name,
                    email, datetime.now(), datetime.now()
                ))
                
                print(f'   [OK] Added {next_client_id}: {new_account} - {company_name}')
                print(f'       Contact: {full_name} | Transactions: {trans_count} | Value: {lifetime}')
                next_client_id += 1
                square_added += 1
                
                # Limit to top 10 missing to avoid too many inserts
                if square_added >= 10:
                    break
            
            # 3. Check for any other high-value missing customers from customer_name_mapping
            print(f'\n🔗 CHECKING CUSTOMER NAME MAPPING FOR ADDITIONAL FIXES:')
            
            cur.execute("""
                SELECT DISTINCT lms_company_name, lms_account_no
                FROM customer_name_mapping 
                WHERE lms_company_name IS NOT NULL 
                AND lms_company_name != ''
                AND match_confidence < 1.0
                AND lms_company_name NOT IN (
                    SELECT company_name FROM clients WHERE company_name IS NOT NULL
                )
                LIMIT 5
            """)
            
            mapping_missing = cur.fetchall()
            mapping_added = 0
            
            for company_name, lms_account in mapping_missing:
                if not company_name.strip():
                    continue
                    
                # Insert new client
                cur.execute("""
                    INSERT INTO clients (
                        client_id, account_number, company_name, client_name,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    next_client_id, lms_account or f'LMS{next_client_id}', 
                    company_name, company_name,
                    datetime.now(), datetime.now()
                ))
                
                print(f'   [OK] Added {next_client_id}: {company_name} (from mapping)')
                next_client_id += 1
                mapping_added += 1
            
            # Commit all changes
            conn.commit()
            
            # Summary
            print(f'\n📊 SUMMARY OF FIXES:')
            print(f'   • LMS Enhanced customers added: {lms_added}')
            print(f'   • Square customers added: {square_added}')
            print(f'   • Mapping customers added: {mapping_added}')
            print(f'   • Total new clients added: {lms_added + square_added + mapping_added}')
            print(f'   • New max client_id: {next_client_id - 1}')
            
            # Verify the fixes
            print(f'\n[OK] VERIFICATION:')
            
            # Check total client count
            cur.execute("SELECT COUNT(*) FROM clients")
            new_total = cur.fetchone()[0]
            print(f'   • Total clients now: {new_total:,}')
            
            # Check if high-value Square customers are now present
            for company in ['Waste Connections of Canada', 'NOVA Chemicals Corporation']:
                cur.execute("SELECT client_id, account_number FROM clients WHERE company_name ILIKE %s", (f'%{company}%',))
                result = cur.fetchone()
                if result:
                    print(f'   • [OK] {company} now exists as client_id {result[0]}')
                else:
                    print(f'   • [FAIL] {company} still missing')

if __name__ == "__main__":
    main()