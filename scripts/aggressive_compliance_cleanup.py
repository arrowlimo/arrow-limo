"""Remove ALL compliance notes - aggressive cleanup"""
import psycopg2
import re

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

# Get ALL charters with any compliance-related text
cur.execute("""
    SELECT charter_id, reserve_number, notes
    FROM charters
    WHERE notes IS NOT NULL
      AND (notes ILIKE '%COMPLIANCE%' 
           OR notes ILIKE '%GST exempt%'
           OR notes ILIKE '%gratuity%'
           OR notes ILIKE '%CRA%'
           OR notes ILIKE '%reparented%')
""")

charters = cur.fetchall()

print(f"\nFound {len(charters)} charters with compliance-related text\n")

updated = 0

for charter_id, reserve_number, notes in charters:
    original_notes = notes
    
    # Remove all compliance patterns (case-insensitive, aggressive)
    cleaned = notes
    
    # List of patterns to remove
    patterns = [
        r'\[COMPLIANCE FIX:[^\]]*\]',
        r'Pre-2013 gratuity:[^\n]*',
        r'Gratuity reparented[^\n]*',
        r'Not included in employer revenue[^\n]*',
        r'GST exempt[^\n]*',
        r'Direct tips paid by customer[^\n]*',
        r'T4 employment income per CRA guidelines[^\n]*',
    ]
    
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Clean up whitespace
    cleaned = re.sub(r'\n\s*\n+', '\n\n', cleaned)  # Multiple newlines to double
    cleaned = cleaned.strip()
    
    if cleaned != original_notes:
        cur.execute("""
            UPDATE charters
            SET notes = %s,
                updated_at = NOW()
            WHERE charter_id = %s
        """, (cleaned if cleaned else None, charter_id))
        
        print(f"✅ {reserve_number}: Cleaned notes")
        if reserve_number == '007032':
            print(f"   BEFORE: {repr(original_notes[:100])}")
            print(f"   AFTER:  {repr(cleaned[:100] if cleaned else 'NULL')}")
        updated += 1

conn.commit()

print(f"\n✅ Updated {updated} charters")
print(f"✅ Changes committed")

cur.close()
conn.close()
