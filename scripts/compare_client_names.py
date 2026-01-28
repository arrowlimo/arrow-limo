#!/usr/bin/env python3
"""
Compare Client Names Across Customer Admin Tables
=================================================

Compares client names between almsdata.clients and customer admin tables
"""

import psycopg2
import os
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

PG_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '')
}

def main():
    print('🔍 COMPARING CLIENT NAMES ACROSS CUSTOMER ADMIN TABLES')
    print('=' * 60)

    with psycopg2.connect(**PG_CONFIG) as conn:
        with conn.cursor() as cur:
            
            # Get all client names from main clients table
            print('📋 Getting client names from main CLIENTS table...')
            cur.execute("""
                SELECT client_id, account_number, company_name, client_name
                FROM clients 
                WHERE company_name IS NOT NULL AND company_name != ''
                ORDER BY client_id
            """)
            
            main_clients = {}
            main_companies = set()
            for row in cur.fetchall():
                client_id, account_no, company_name, client_name = row
                main_clients[client_id] = {
                    'account_number': account_no,
                    'company_name': company_name,
                    'client_name': client_name
                }
                main_companies.add(company_name.strip().lower())
            
            print(f'   Found {len(main_clients):,} clients with company names')
            
            # Check lms_customers_enhanced 
            print('\n📋 Checking LMS_CUSTOMERS_ENHANCED table...')
            cur.execute("""
                SELECT account_no, primary_name, company_name, full_name_search
                FROM lms_customers_enhanced 
                WHERE company_name IS NOT NULL AND company_name != ''
                LIMIT 20
            """)
            
            lms_enhanced = cur.fetchall()
            print(f'   Sample LMS Enhanced customers:')
            missing_in_main = []
            found_in_main = []
            
            for row in lms_enhanced:
                account_no, primary_name, company_name, full_name_search = row
                company_clean = company_name.strip().lower() if company_name else ''
                
                if company_clean and company_clean in main_companies:
                    found_in_main.append((account_no, company_name))
                elif company_clean and company_clean not in main_companies:
                    missing_in_main.append((account_no, company_name))
                
                print(f'     {account_no}: {company_name} | Primary: {primary_name}')
            
            print(f'\n   [OK] {len(found_in_main)} LMS companies found in main clients')
            print(f'   [FAIL] {len(missing_in_main)} LMS companies NOT found in main clients')
            
            if missing_in_main:
                print(f'\n   Missing companies (first 5):')
                for account, company in missing_in_main[:5]:
                    print(f'     {account}: {company}')
            
            # Check customer_name_mapping
            print('\n📋 Checking CUSTOMER_NAME_MAPPING table...')
            cur.execute("""
                SELECT alms_client_id, alms_account_number, alms_company_name, 
                       lms_account_no, lms_company_name, match_confidence
                FROM customer_name_mapping 
                WHERE alms_company_name IS NOT NULL 
                ORDER BY match_confidence DESC
                LIMIT 20
            """)
            
            mappings = cur.fetchall()
            print(f'   Sample mappings (confidence sorted):')
            perfect_matches = 0
            for row in mappings:
                alms_id, alms_account, alms_company, lms_account, lms_company, confidence = row
                if confidence == 1.0:
                    perfect_matches += 1
                print(f'     ALMS: {alms_company} | LMS: {lms_company} | Conf: {confidence}')
            
            print(f'\n   🎯 {perfect_matches} perfect confidence matches found')
            
            # Check qb_export_customers
            print('\n📋 Checking QB_EXPORT_CUSTOMERS table...')
            cur.execute("""
                SELECT "Account Number", "Customer", "Company", "Email", "Status"
                FROM qb_export_customers 
                WHERE "Company" IS NOT NULL AND "Company" != ''
                ORDER BY "Account Number"
                LIMIT 15
            """)
            
            qb_customers = cur.fetchall()
            qb_missing = []
            qb_found = []
            
            print(f'   Sample QB customers:')
            for row in qb_customers:
                account_no, customer, company, email, status = row
                company_clean = company.strip().lower() if company else ''
                
                if company_clean in main_companies:
                    qb_found.append((account_no, company))
                else:
                    qb_missing.append((account_no, company))
                
                print(f'     {account_no}: {company} | Status: {status}')
            
            print(f'\n   [OK] {len(qb_found)} QB companies found in main clients')
            print(f'   [FAIL] {len(qb_missing)} QB companies NOT found in main clients')
            
            # Check square_customers
            print('\n📋 Checking SQUARE_CUSTOMERS table...')
            cur.execute("""
                SELECT first_name, surname, company_name, email_address, 
                       transaction_count, lifetime_spend
                FROM square_customers 
                WHERE company_name IS NOT NULL AND company_name != ''
                ORDER BY transaction_count DESC
                LIMIT 10
            """)
            
            square_customers = cur.fetchall()
            square_found = []
            square_missing = []
            
            print(f'   Sample Square customers with companies:')
            for row in square_customers:
                first_name, surname, company_name, email, trans_count, lifetime = row
                company_clean = company_name.strip().lower() if company_name else ''
                
                if company_clean in main_companies:
                    square_found.append(company_name)
                else:
                    square_missing.append(company_name)
                
                print(f'     {first_name} {surname} | {company_name} | {trans_count} trans | {lifetime}')
            
            print(f'\n   [OK] {len(square_found)} Square companies found in main clients')
            print(f'   [FAIL] {len(square_missing)} Square companies NOT found in main clients')
            
            # Summary
            print(f'\n📊 SUMMARY:')
            print(f'   • Main clients table: {len(main_clients):,} clients')
            print(f'   • LMS Enhanced: {len(lms_enhanced):,} sampled')
            print(f'   • Customer Mappings: {len(mappings):,} sampled ({perfect_matches} perfect matches)')
            print(f'   • QB Export: {len(qb_customers):,} sampled')
            print(f'   • Square Customers: {len(square_customers):,} with companies')

if __name__ == "__main__":
    main()