#!/usr/bin/env python3
"""
Recheck and reclassify misscoded names:
1. Identify obvious company names (like "Edwards, Garage")
2. Reset them to corporate_parent_id=1 (uncertain)
3. Restore backwards names if detected
4. Handle family member patterns (Betty and Ernie Smith)
"""
import os
import psycopg2
import re

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def is_likely_company(last_name, first_name):
    """Heuristics to detect company names misclassified as individuals"""
    if not last_name or not first_name:
        return False
    
    # Company keywords
    company_keywords = [
        'inc', 'ltd', 'corp', 'company', 'co', 'llc', 'industries', 'services',
        'solutions', 'group', 'holdings', 'enterprises', 'systems', 'international',
        'global', 'associates', 'partners', 'consultants', 'management', 'agency',
        'bank', 'insurance', 'hospital', 'clinic', 'school', 'college', 'university',
        'hotel', 'restaurant', 'café', 'bar', 'pub', 'lounge', 'nightclub', 'club',
        'garage', 'automotive', 'dealership', 'motor', 'truck', 'pipeline', 'pipeline',
        'airline', 'aviation', 'transport', 'logistics', 'shipping', 'freight',
        'construction', 'excavation', 'engineering', 'architecture', 'design',
        'manufacturing', 'factory', 'plant', 'mill', 'foundation', 'society',
        'association', 'organization', 'union', 'cooperative', 'credit union',
        'chemicals', 'energy', 'oil', 'gas', 'mining', 'agriculture', 'farming'
    ]
    
    combined = f"{last_name} {first_name}".lower()
    for keyword in company_keywords:
        if keyword in combined:
            return True
    
    # Multi-word last names are usually companies
    if len(last_name.split()) > 1:
        return True
    
    return False

def is_backward_name(last_name, first_name):
    """Detect if name is backwards (First Last → should be Last, First)"""
    if not last_name or not first_name:
        return False
    
    # If both are single words and don't contain special patterns
    if len(last_name.split()) == 1 and len(first_name.split()) == 1:
        # Check if pattern looks reversed (last_name looks more like first name)
        # Very basic heuristic: single letter last names are suspicious
        if len(last_name) == 1 and len(first_name) > 3:
            return True
    
    return False

def is_family_member(last_name, first_name):
    """Detect family member entries like 'Betty and Ernie Smith'"""
    if not last_name or not first_name:
        return False
    
    combined = f"{last_name} {first_name}".lower()
    if ' and ' in combined:
        return True
    if ' & ' in combined:
        return True
    
    return False

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("RECHECK AND RECLASSIFY: Identify misscoded names")
    print("=" * 80)
    
    # Get all individuals with split names
    cur.execute("""
        SELECT 
            client_id, 
            company_name, 
            last_name, 
            first_name,
            corporate_parent_id
        FROM clients
        WHERE corporate_parent_id = 0 
          AND first_name IS NOT NULL
          AND last_name IS NOT NULL
        ORDER BY client_id
    """)
    
    all_records = cur.fetchall()
    
    misclassified_companies = []
    backward_names = []
    family_members = []
    
    print(f"\nAnalyzing {len(all_records)} individuals...")
    
    for client_id, company_name, last_name, first_name, corp_parent in all_records:
        if is_likely_company(last_name, first_name):
            misclassified_companies.append((client_id, company_name, last_name, first_name))
        
        if is_backward_name(last_name, first_name):
            backward_names.append((client_id, company_name, last_name, first_name))
        
        if is_family_member(last_name, first_name):
            family_members.append((client_id, company_name, last_name, first_name))
    
    # Report findings
    print(f"\n" + "=" * 80)
    print(f"FINDINGS:")
    print(f"=" * 80)
    print(f"Likely misclassified companies:  {len(misclassified_companies)}")
    print(f"Possible backward names:        {len(backward_names)}")
    print(f"Family member entries:          {len(family_members)}")
    
    # Show samples
    if misclassified_companies:
        print(f"\n📋 SAMPLE MISCLASSIFIED COMPANIES (first 20):")
        for client_id, company_name, last_name, first_name in misclassified_companies[:20]:
            print(f"  ID {client_id}: '{company_name}' (parsed as: '{first_name}' / '{last_name}')")
        
        response = input(f"\nReset {len(misclassified_companies)} misclassified companies to corporate_parent_id=1? [y/N]: ").strip().lower()
        if response == 'y':
            for client_id, _, _, _ in misclassified_companies:
                cur.execute("""
                    UPDATE clients
                    SET corporate_parent_id = 1
                    WHERE client_id = %s
                """, (client_id,))
            conn.commit()
            print(f"✅ Reset {len(misclassified_companies)} companies")
    
    if backward_names:
        print(f"\n📋 SAMPLE BACKWARD NAMES (first 20):")
        for client_id, company_name, last_name, first_name in backward_names[:20]:
            print(f"  ID {client_id}: '{first_name}, {last_name}' (might be: '{last_name}, {first_name}')")
        
        response = input(f"\nReverse {len(backward_names)} backward names? [y/N]: ").strip().lower()
        if response == 'y':
            for client_id, _, last_name, first_name in backward_names:
                cur.execute("""
                    UPDATE clients
                    SET 
                        first_name = %s,
                        last_name = %s,
                        company_name = %s
                    WHERE client_id = %s
                """, (last_name, first_name, f"{first_name}, {last_name}", client_id))
            conn.commit()
            print(f"✅ Reversed {len(backward_names)} names")
    
    if family_members:
        print(f"\n📋 SAMPLE FAMILY MEMBERS (first 20):")
        for client_id, company_name, last_name, first_name in family_members[:20]:
            print(f"  ID {client_id}: '{company_name}' (contains 'and')")
        
        print(f"\n⚠️  {len(family_members)} family member entries remain as individuals")
        print("   (Multiple names on same charter - OK to keep as-is)")
    
    # Final verification
    print(f"\n" + "=" * 80)
    print(f"FINAL STATE:")
    print(f"=" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE corporate_parent_id = 0) as individuals,
            COUNT(*) FILTER (WHERE corporate_parent_id = 1) as uncertain,
            COUNT(*) as total
        FROM clients;
    """)
    
    individuals, uncertain, total = cur.fetchone()
    print(f"corporate_parent_id = 0:  {individuals} (individuals)")
    print(f"corporate_parent_id = 1:  {uncertain} (uncertain/companies)")
    print(f"Total:                    {total}")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    if conn:
        conn.rollback()
        conn.close()
    exit(1)
