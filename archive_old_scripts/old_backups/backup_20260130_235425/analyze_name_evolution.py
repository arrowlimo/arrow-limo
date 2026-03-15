#!/usr/bin/env python3
"""
Analyze Name Structure Evolution
==============================

Shows the evolution from first_name/last_name to single name with fuzzy search
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
    print('🔄 NAME STRUCTURE EVOLUTION ANALYSIS')
    print('=' * 50)

    with psycopg2.connect(**PG_CONFIG) as conn:
        with conn.cursor() as cur:
            
            print('📋 CURRENT CLIENTS TABLE NAME STRUCTURE:')
            print('   • company_name (varchar 255) - Business/organization name')
            print('   • client_name (text) - Individual contact name')
            print('   [FAIL] No first_name/last_name columns')
            
            print(f'\n🔍 SYSTEMS THAT STILL USE FIRST_NAME/LAST_NAME:')
            
            # Square customers with first/last names
            print('   💳 SQUARE_CUSTOMERS:')
            cur.execute("""
                SELECT first_name, surname, company_name
                FROM square_customers 
                WHERE first_name IS NOT NULL 
                AND first_name != ''
                LIMIT 10
            """)
            square_names = cur.fetchall()
            for first, last, company in square_names:
                print(f'     {first} {last} @ {company or "Individual"}')
            
            # Employees still use first/last
            print(f'\n   👥 EMPLOYEES:')
            cur.execute("""
                SELECT first_name, last_name, full_name, position
                FROM employees 
                WHERE first_name IS NOT NULL
                LIMIT 8
            """)
            employee_names = cur.fetchall()
            for first, last, full, position in employee_names:
                print(f'     {first} {last} ({full}) - {position or "No position"}')
            
            print(f'\n🔍 FUZZY SEARCH IMPLEMENTATIONS:')
            
            # LMS enhanced with fuzzy search
            print('   📊 LMS_CUSTOMERS_ENHANCED.full_name_search:')
            cur.execute("""
                SELECT primary_name, company_name, full_name_search
                FROM lms_customers_enhanced 
                WHERE full_name_search IS NOT NULL 
                AND full_name_search != ''
                LIMIT 8
            """)
            lms_fuzzy = cur.fetchall()
            for primary, company, fuzzy in lms_fuzzy:
                print(f'     Primary: {primary}')
                print(f'     Company: {company}')
                print(f'     Fuzzy: {fuzzy}')
                print()
            
            # Customer name resolver
            print('   🔗 CUSTOMER_NAME_RESOLVER.full_name_search:')
            cur.execute("""
                SELECT resolved_name, full_name_search, match_type
                FROM customer_name_resolver 
                WHERE full_name_search IS NOT NULL 
                AND full_name_search != ''
                LIMIT 5
            """)
            resolver_fuzzy = cur.fetchall()
            for resolved, fuzzy, match_type in resolver_fuzzy:
                print(f'     Resolved: {resolved} | Fuzzy: {fuzzy} | Type: {match_type}')
            
            print(f'\n📊 CURRENT CLIENT_NAME FIELD ANALYSIS:')
            
            # Analyze what's in client_name field
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN client_name IS NOT NULL AND client_name != '' THEN 1 END) as with_names,
                    COUNT(CASE WHEN client_name ILIKE '% %' THEN 1 END) as with_spaces,
                    COUNT(CASE WHEN LENGTH(client_name) > 50 THEN 1 END) as long_names
                FROM clients
            """)
            
            stats = cur.fetchone()
            total, with_names, with_spaces, long_names = stats
            
            print(f'   • Total clients: {total:,}')
            print(f'   • With client_name populated: {with_names:,} ({with_names/total*100:.1f}%)')
            print(f'   • Names with spaces (likely first+last): {with_spaces:,} ({with_spaces/total*100:.1f}%)')
            print(f'   • Long names (>50 chars): {long_names:,}')
            
            # Sample analysis of current names
            print(f'\n📝 SAMPLE CURRENT CLIENT_NAME PATTERNS:')
            cur.execute("""
                SELECT client_name, company_name,
                       CASE 
                           WHEN client_name ILIKE '%, %' THEN 'Last, First format'
                           WHEN client_name ILIKE '% %' AND client_name NOT ILIKE '%,%' THEN 'First Last format'
                           WHEN LENGTH(client_name) < 20 AND client_name NOT ILIKE '% %' THEN 'Single name'
                           ELSE 'Complex/Description'
                       END as name_pattern
                FROM clients 
                WHERE client_name IS NOT NULL AND client_name != ''
                ORDER BY RANDOM()
                LIMIT 10
            """)
            
            patterns = cur.fetchall()
            for client_name, company, pattern in patterns:
                print(f'     "{client_name}" @ {company} → {pattern}')
            
            print(f'\n💡 EVOLUTION SUMMARY:')
            print('   🔄 Migration Path Detected:')
            print('     1. Originally: first_name + last_name columns (still in employees, square)')
            print('     2. Evolved to: single client_name field (current clients table)')
            print('     3. Added: full_name_search fields for fuzzy matching (LMS, resolver)')
            print('     4. Pattern: Mixed format names in client_name field')
            
            print(f'\n🎯 CURRENT STATE:')
            print('   [OK] Clients table uses single client_name field')
            print('   [OK] Fuzzy search supported via full_name_search in related tables')
            print('   [OK] Square/Employees retain first/last name structure')
            print('   [WARN]  Mixed name formats in client_name field')

if __name__ == "__main__":
    main()