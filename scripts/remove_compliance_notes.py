"""Remove GST/controlled tips compliance notes from charters"""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

# Find all charters with compliance notes
cur.execute("""
    SELECT charter_id, reserve_number, notes
    FROM charters
    WHERE notes ILIKE '%COMPLIANCE FIX%'
       OR notes ILIKE '%GST exempt%'
       OR notes ILIKE '%controlled tips%'
       OR notes ILIKE '%Gratuity reparented%'
       OR notes ILIKE '%Pre-2013 gratuity%'
       OR notes ILIKE '%CRA guidelines%'
""")

affected = cur.fetchall()

print(f"\n{'='*80}")
print(f"FOUND {len(affected)} CHARTERS WITH COMPLIANCE NOTES")
print(f"{'='*80}\n")

cleaned = 0

for charter_id, reserve_number, notes in affected:
    if not notes:
        continue
    
    # Remove all compliance-related text
    cleaned_notes = notes
    
    # Remove specific compliance patterns
    patterns_to_remove = [
        "[COMPLIANCE FIX: Gratuity reparented as customer tip - GST exempt]",
        "Pre-2013 gratuity: Direct tips paid by customer to driver. Not included in employer revenue or T4 employment income per CRA guidelines.",
        "[COMPLIANCE FIX: Gratuity reparented as customer tip - GST exempt]\n",
        "\n[COMPLIANCE FIX: Gratuity reparented as customer tip - GST exempt]",
        "\nPre-2013 gratuity: Direct tips paid by customer to driver. Not included in employer revenue or T4 employment income per CRA guidelines.",
        "Pre-2013 gratuity: Direct tips paid by customer to driver. Not included in employer revenue or T4 employment income per CRA guidelines.\n",
    ]
    
    for pattern in patterns_to_remove:
        cleaned_notes = cleaned_notes.replace(pattern, "")
    
    # Clean up extra whitespace/newlines
    cleaned_notes = cleaned_notes.strip()
    
    # Update if changed
    if cleaned_notes != notes:
        cur.execute("""
            UPDATE charters
            SET notes = %s,
                updated_at = NOW()
            WHERE charter_id = %s
        """, (cleaned_notes if cleaned_notes else None, charter_id))
        
        print(f"✅ {reserve_number}: Removed compliance notes")
        cleaned += 1
    else:
        print(f"⚠️  {reserve_number}: No changes needed")

conn.commit()

print(f"\n{'='*80}")
print(f"SUMMARY:")
print(f"{'='*80}")
print(f"Charters found: {len(affected)}")
print(f"Charters cleaned: {cleaned}")
print(f"✅ Changes committed to database")

cur.close()
conn.close()
