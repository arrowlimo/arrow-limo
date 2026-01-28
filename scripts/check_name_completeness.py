#!/usr/bin/env python3
"""
Check Name Column Completeness
=============================

Analyzes if all name columns are populated across the database
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
    print('🔍 CHECKING NAME COLUMN COMPLETENESS')
    print('=' * 50)

    with psycopg2.connect(**PG_CONFIG) as conn:
        with conn.cursor() as cur:
            
            # Check clients table name completeness
            print('📋 CLIENTS TABLE NAME ANALYSIS:')
            cur.execute("""
                SELECT 
                    COUNT(*) as total_clients,
                    COUNT(CASE WHEN company_name IS NOT NULL AND company_name != '' THEN 1 END) as has_company_name,
                    COUNT(CASE WHEN client_name IS NOT NULL AND client_name != '' THEN 1 END) as has_client_name,
                    COUNT(CASE WHEN company_name IS NULL OR company_name = '' THEN 1 END) as missing_company_name,
                    COUNT(CASE WHEN client_name IS NULL OR client_name = '' THEN 1 END) as missing_client_name,
                    COUNT(CASE WHEN (company_name IS NULL OR company_name = '') 
                                AND (client_name IS NULL OR client_name = '') THEN 1 END) as missing_both_names
                FROM clients
            """)
            
            stats = cur.fetchone()
            total, has_company, has_client, missing_company, missing_client, missing_both = stats
            
            print(f'   📊 Total clients: {total:,}')
            print(f'   [OK] Has company_name: {has_company:,} ({has_company/total*100:.1f}%)')
            print(f'   [OK] Has client_name: {has_client:,} ({has_client/total*100:.1f}%)')
            print(f'   [FAIL] Missing company_name: {missing_company:,} ({missing_company/total*100:.1f}%)')
            print(f'   [FAIL] Missing client_name: {missing_client:,} ({missing_client/total*100:.1f}%)')
            print(f'   🚨 Missing BOTH names: {missing_both:,} ({missing_both/total*100:.1f}%)')
            
            # Show examples of missing names
            if missing_client > 0:
                print(f'\n📝 EXAMPLES OF CLIENTS MISSING client_name:')
                cur.execute("""
                    SELECT client_id, account_number, company_name, client_name
                    FROM clients 
                    WHERE client_name IS NULL OR client_name = ''
                    ORDER BY client_id DESC
                    LIMIT 10
                """)
                
                missing_examples = cur.fetchall()
                print('   ID    Account   Company Name                    Client Name')
                print('   ' + '-' * 65)
                for row in missing_examples:
                    client_id, account, company, client = row
                    company_str = (company or 'None')[:25]
                    client_str = (client or 'MISSING')[:20]
                    print(f'   {client_id:<5} {account:<9} {company_str:<30} {client_str}')
            
            if missing_both > 0:
                print(f'\n🚨 EXAMPLES OF CLIENTS MISSING BOTH NAMES:')
                cur.execute("""
                    SELECT client_id, account_number, email, created_at
                    FROM clients 
                    WHERE (company_name IS NULL OR company_name = '') 
                    AND (client_name IS NULL OR client_name = '')
                    ORDER BY client_id DESC
                    LIMIT 5
                """)
                
                both_missing = cur.fetchall()
                for row in both_missing:
                    client_id, account, email, created = row
                    print(f'   ID {client_id}: Account {account} | Email: {email or "None"} | Created: {created}')
            
            # Check other tables with name fields
            print(f'\n📋 OTHER TABLES NAME COMPLETENESS:')
            
            # Employees
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN first_name IS NOT NULL AND first_name != '' THEN 1 END) as has_first,
                    COUNT(CASE WHEN last_name IS NOT NULL AND last_name != '' THEN 1 END) as has_last,
                    COUNT(CASE WHEN full_name IS NOT NULL AND full_name != '' THEN 1 END) as has_full
                FROM employees
            """)
            emp_stats = cur.fetchone()
            total_emp, has_first, has_last, has_full = emp_stats
            print(f'   👥 EMPLOYEES ({total_emp:,} total):')
            print(f'      First name: {has_first:,}/{total_emp} ({has_first/total_emp*100:.1f}%)')
            print(f'      Last name: {has_last:,}/{total_emp} ({has_last/total_emp*100:.1f}%)')
            print(f'      Full name: {has_full:,}/{total_emp} ({has_full/total_emp*100:.1f}%)')
            
            # Square customers
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN first_name IS NOT NULL AND first_name != '' THEN 1 END) as has_first,
                    COUNT(CASE WHEN surname IS NOT NULL AND surname != '' THEN 1 END) as has_last,
                    COUNT(CASE WHEN company_name IS NOT NULL AND company_name != '' THEN 1 END) as has_company
                FROM square_customers
            """)
            sq_stats = cur.fetchone()
            total_sq, has_first_sq, has_last_sq, has_company_sq = sq_stats
            print(f'   💳 SQUARE CUSTOMERS ({total_sq:,} total):')
            print(f'      First name: {has_first_sq:,}/{total_sq} ({has_first_sq/total_sq*100:.1f}%)')
            print(f'      Surname: {has_last_sq:,}/{total_sq} ({has_last_sq/total_sq*100:.1f}%)')
            print(f'      Company name: {has_company_sq:,}/{total_sq} ({has_company_sq/total_sq*100:.1f}%)')
            
            # LMS Enhanced
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN primary_name IS NOT NULL AND primary_name != '' THEN 1 END) as has_primary,
                    COUNT(CASE WHEN company_name IS NOT NULL AND company_name != '' THEN 1 END) as has_company,
                    COUNT(CASE WHEN full_name_search IS NOT NULL AND full_name_search != '' THEN 1 END) as has_fuzzy
                FROM lms_customers_enhanced
            """)
            lms_stats = cur.fetchone()
            total_lms, has_primary, has_company_lms, has_fuzzy = lms_stats
            print(f'   📊 LMS ENHANCED ({total_lms:,} total):')
            print(f'      Primary name: {has_primary:,}/{total_lms} ({has_primary/total_lms*100:.1f}%)')
            print(f'      Company name: {has_company_lms:,}/{total_lms} ({has_company_lms/total_lms*100:.1f}%)')
            print(f'      Fuzzy search: {has_fuzzy:,}/{total_lms} ({has_fuzzy/total_lms*100:.1f}%)')
            
            # Summary of name completeness across system
            print(f'\n📊 SYSTEM-WIDE NAME COMPLETENESS SUMMARY:')
            
            total_name_records = total + total_emp + total_sq + total_lms
            total_with_some_name = has_company + has_client + has_full + has_first_sq + has_primary
            
            print(f'   🎯 Overall Assessment:')
            print(f'      • Main clients table: {(has_client/total*100):.1f}% have client names')
            print(f'      • Employees: {(has_full/total_emp*100):.1f}% have full names')
            print(f'      • Square customers: {(has_first_sq/total_sq*100):.1f}% have first names')
            print(f'      • LMS enhanced: {(has_fuzzy/total_lms*100):.1f}% have fuzzy search names')
            
            # Check for potential data quality issues
            print(f'\n[WARN]  POTENTIAL DATA QUALITY ISSUES:')
            
            # Very short names (might be incomplete)
            cur.execute("""
                SELECT COUNT(*) FROM clients 
                WHERE client_name IS NOT NULL 
                AND LENGTH(TRIM(client_name)) <= 2
            """)
            short_names = cur.fetchone()[0]
            if short_names > 0:
                print(f'   • {short_names} clients with very short names (≤2 chars)')
            
            # Names that look like placeholders
            cur.execute("""
                SELECT COUNT(*) FROM clients 
                WHERE client_name ILIKE '%unknown%' 
                OR client_name ILIKE '%test%'
                OR client_name ILIKE '%temp%'
                OR client_name = 'N/A'
            """)
            placeholder_names = cur.fetchone()[0]
            if placeholder_names > 0:
                print(f'   • {placeholder_names} clients with placeholder-like names')
            
            print(f'\n[OK] CONCLUSION: {"Good" if missing_client < total*0.05 else "Needs Attention"} name completeness overall')

if __name__ == "__main__":
    main()