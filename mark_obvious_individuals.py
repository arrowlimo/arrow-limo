#!/usr/bin/env python3
"""
Mark obvious individual names (two-word format) as corporate_parent_id=0
Create list of uncertain cases for manual review
"""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def is_obvious_individual(text):
    """
    Mark as individual if:
    - Exactly 2 words, both capitalized, both alphabetic
    - Examples: "Barnes Sara", "White Bill", "Schapansky Megan", "John Smith"
    """
    if not text or ',' in text:
        return False
    
    words = text.strip().split()
    
    # Exactly 2 words
    if len(words) != 2:
        return False
    
    # Both capitalized and alphabetic
    return (words[0].isalpha() and words[0][0].isupper() and 
            words[1].isalpha() and words[1][0].isupper())

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Find all obvious individual names
    print("=" * 80)
    print("STEP 1: Identify obvious individual names (2 capitalized words)")
    print("=" * 80)
    
    cur.execute("""
        SELECT client_id, company_name
        FROM clients
        WHERE corporate_parent_id = 1
        ORDER BY company_name
    """)
    
    obvious_individuals = []
    uncertain = []
    
    for client_id, company_name in cur.fetchall():
        if is_obvious_individual(company_name):
            obvious_individuals.append((client_id, company_name))
        else:
            uncertain.append((client_id, company_name))
    
    print(f"\nObvious individuals (2-word names): {len(obvious_individuals)}")
    print(f"Uncertain/Company names: {len(uncertain)}")
    
    # Show samples
    print("\nSample obvious individuals to mark:")
    for client_id, name in obvious_individuals[:15]:
        words = name.strip().split()
        print(f"  ID {client_id}: '{name}' → last='{words[0]}', first='{words[1]}'")
    if len(obvious_individuals) > 15:
        print(f"  ... and {len(obvious_individuals) - 15} more")
    
    # Confirm
    print("\n" + "=" * 80)
    response = input(f"\nMark {len(obvious_individuals)} obvious individuals as corporate_parent_id=0? [y/N]: ").strip().lower()
    
    if response == 'y':
        print("🔄 Updating...")
        
        for client_id, company_name in obvious_individuals:
            words = company_name.strip().split()
            last_name, first_name = words[0], words[1]
            
            cur.execute("""
                UPDATE clients
                SET 
                    first_name = %s,
                    last_name = %s,
                    corporate_parent_id = 0,
                    corporate_role = NULL
                WHERE client_id = %s
            """, (first_name, last_name, client_id))
        
        conn.commit()
        print(f"✅ Updated {len(obvious_individuals)} clients")
    else:
        print("❌ Cancelled")
        conn.close()
        exit(0)
    
    # Step 2: Show uncertain list for manual review
    print("\n" + "=" * 80)
    print("STEP 2: Uncertain cases (needs manual review/correction)")
    print("=" * 80)
    print(f"\nTotal uncertain: {len(uncertain)}\n")
    
    # Save to file
    with open('reports/clients_need_manual_review.txt', 'w') as f:
        f.write("CLIENTS NEEDING MANUAL CLASSIFICATION\n")
        f.write("=" * 80 + "\n\n")
        f.write("Instructions:\n")
        f.write("- If individual name: mark corporate_parent_id=0 and fill first_name/last_name\n")
        f.write("- If company: mark corporate_parent_id=0 (for now) and note company name\n")
        f.write("- Group related companies later\n\n")
        f.write(f"Total records: {len(uncertain)}\n\n")
        
        for client_id, name in uncertain:
            name_str = str(name or "").strip()
            f.write(f"ID {client_id:6} | {name_str:40}\n")
    
    print(f"📄 Saved uncertain cases to: reports/clients_need_manual_review.txt\n")
    
    # Show preview
    print("Preview (first 20):")
    for client_id, name in uncertain[:20]:
        print(f"  ID {client_id}: {name}")
    if len(uncertain) > 20:
        print(f"  ... and {len(uncertain) - 20} more")
    
    # Final verification
    print("\n" + "=" * 80)
    print("VERIFICATION: Updated state")
    print("=" * 80)
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE corporate_parent_id = 0) as individuals,
            COUNT(*) FILTER (WHERE corporate_parent_id = 1) as parent_1,
            COUNT(*) FILTER (WHERE corporate_parent_id > 1) as other,
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
