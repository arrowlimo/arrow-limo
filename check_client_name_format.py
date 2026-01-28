#!/usr/bin/env python3
"""
Check client_name format (First Last vs Last, First)
"""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Check client_name format for individuals
    print("=" * 80)
    print("INDIVIDUALS (company_name = 'None')")
    print("=" * 80)
    cur.execute("""
        SELECT 
            client_id,
            client_name,
            company_name,
            last_name,
            first_name
        FROM clients
        WHERE company_name = 'None'
        LIMIT 15;
    """)
    
    for row in cur.fetchall():
        client_id, client_name, company_name, last_name, first_name = row
        print(f"ID: {client_id}")
        print(f"  client_name:   '{client_name}'")
        print(f"  company_name:  '{company_name}'")
        print(f"  last_name:     '{last_name}'")
        print(f"  first_name:    '{first_name}'")
        print()
    
    # Check client_name format for companies
    print("=" * 80)
    print("COMPANIES (company_name != 'None')")
    print("=" * 80)
    cur.execute("""
        SELECT 
            client_id,
            client_name,
            company_name,
            last_name,
            first_name
        FROM clients
        WHERE company_name != 'None'
        LIMIT 15;
    """)
    
    for row in cur.fetchall():
        client_id, client_name, company_name, last_name, first_name = row
        print(f"ID: {client_id}")
        print(f"  client_name:   '{client_name}'")
        print(f"  company_name:  '{company_name}'")
        print(f"  last_name:     '{last_name}'")
        print(f"  first_name:    '{first_name}'")
        print()
    
    # Check if client_name matches pattern
    print("=" * 80)
    print("FORMAT ANALYSIS")
    print("=" * 80)
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE client_name LIKE '%,%') as has_comma,
            COUNT(*) FILTER (WHERE company_name = 'None') as individuals,
            COUNT(*) FILTER (WHERE company_name != 'None') as companies
        FROM clients;
    """)
    
    total, has_comma, individuals, companies = cur.fetchone()
    print(f"Total clients:      {total}")
    print(f"With comma format:  {has_comma}")
    print(f"Individuals (None): {individuals}")
    print(f"Companies:          {companies}")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
