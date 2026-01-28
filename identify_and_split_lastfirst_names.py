#!/usr/bin/env python3
"""
Identify and split "Last First" format names (no comma)
Examples: "Barnes Sara", "White Bill", "Schapansky Megan"
"""
import os
import psycopg2
import re

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def looks_like_individual_name(text):
    """
    Heuristic: exactly 2 words, both capitalized → likely "Last First" format
    Examples: "Barnes Sara", "White Bill", "Schapansky Megan"
    Returns True if name should be split
    """
    if not text or ',' in text:  # Skip if already has comma
        return False
    
    words = text.strip().split()
    
    # Exactly 2 words
    if len(words) != 2:
        return False
    
    # Both words should start with capital letter (proper names)
    word1, word2 = words
    if not (word1[0].isupper() and word2[0].isupper()):
        return False
    
    # Both should be alphabetic (no numbers/special chars)
    if not (word1.isalpha() and word2.isalpha()):
        return False
    
    # Exclude known company patterns
    known_companies = ['arrow', 'limousine', 'limo', 'transport', 'services', 'ltd', 'inc', 'corp', 'co']
    combined = (word1 + word2).lower()
    for comp in known_companies:
        if comp in combined:
            return False
    
    return True

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Step 1: Find candidates
    print("=" * 80)
    print("CANDIDATES: Two-word names without comma (likely Last First format)")
    print("=" * 80)
    
    cur.execute("""
        SELECT client_id, company_name, client_name, first_name, last_name
        FROM clients
        WHERE company_name IS NOT NULL
          AND company_name NOT LIKE '%,%'
          AND first_name IS NULL
          AND last_name IS NULL
        ORDER BY company_name
    """)
    
    candidates = []
    for client_id, company_name, client_name, first_name, last_name in cur.fetchall():
        if looks_like_individual_name(company_name):
            words = company_name.strip().split()
            candidates.append((client_id, company_name, words[0], words[1]))
    
    print(f"\nFound {len(candidates)} candidates:\n")
    for client_id, company_name, last_name, first_name in candidates[:30]:
        print(f"  ID {client_id}: '{company_name}' → last='{last_name}', first='{first_name}'")
    
    if len(candidates) > 30:
        print(f"  ... and {len(candidates) - 30} more")
    
    # Step 2: Ask for confirmation
    print("\n" + "=" * 80)
    response = input(f"\nSplit these {len(candidates)} names into individual clients (corporate_parent_id=0)? [y/N]: ").strip().lower()
    
    if response == 'y':
        print("🔄 Updating...")
        
        updated_count = 0
        for client_id, company_name, last_name, first_name in candidates:
            cur.execute("""
                UPDATE clients
                SET 
                    first_name = %s,
                    last_name = %s,
                    corporate_parent_id = 0,
                    corporate_role = NULL
                WHERE client_id = %s
            """, (first_name, last_name, client_id))
            updated_count += cur.rowcount
        
        conn.commit()
        print(f"✅ Updated {updated_count} clients")
    else:
        print("❌ Cancelled")
        conn.rollback()
        conn.close()
        exit(0)
    
    # Step 3: Final verification
    print("\n" + "=" * 80)
    print("VERIFICATION: Current state")
    print("=" * 80)
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE corporate_parent_id = 0) as individuals,
            COUNT(*) FILTER (WHERE corporate_parent_id = 1) as parent_company_1,
            COUNT(*) FILTER (WHERE corporate_parent_id > 1) as other_parents,
            COUNT(*) as total
        FROM clients;
    """)
    
    individuals, parent_1, other, total = cur.fetchone()
    print(f"corporate_parent_id = 0:  {individuals}")
    print(f"corporate_parent_id = 1:  {parent_1}")
    print(f"corporate_parent_id > 1:  {other}")
    print(f"Total:                    {total}")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    if conn:
        conn.rollback()
        conn.close()
    exit(1)
