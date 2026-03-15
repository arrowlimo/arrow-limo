"""
Search for client records matching the names from the screenshots
and get their client_id values to reassign the charters
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='ArrowLimousine'
)
cur = conn.cursor()

print("="*80)
print("FINDING CLIENT RECORDS")
print("="*80)

# Search patterns based on screenshots
search_patterns = [
    ('Fort Sask', 'Rangers'),
    ('Exxonrev', None),
    ('Meyers', 'Jennifer'),
    ('Jennifer', 'Meyers'),
]

print("\nSearching clients table...")

# First, let's see if there's a clients table
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name LIKE '%client%'
""")
tables = cur.fetchall()
print(f"\nClient-related tables: {[t[0] for t in tables]}")

# Look for clients with similar names
print("\n" + "="*80)
print("SEARCHING FOR CLIENTS")
print("="*80)

# Search in charters for distinct client names and IDs
cur.execute("""
    SELECT DISTINCT client_id, client_display_name
    FROM charters
    WHERE client_display_name ILIKE '%fort%sask%'
       OR client_display_name ILIKE '%exxon%'
       OR client_display_name ILIKE '%meyers%'
       OR client_display_name ILIKE '%jennifer%'
    ORDER BY client_display_name
""")

potential_clients = cur.fetchall()
if potential_clients:
    print("\nFound potential matches:")
    for client_id, client_name in potential_clients:
        print(f"  ID {client_id}: {client_name}")
else:
    print("\nNo matches found in charters table")

# Check if there's a separate clients table
cur.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'clients'
    )
""")
has_clients_table = cur.fetchone()[0]

if has_clients_table:
    print("\n" + "="*80)
    print("SEARCHING CLIENTS TABLE")
    print("="*80)
    
    cur.execute("""
        SELECT client_id, client_name, display_name, company_name
        FROM clients
        WHERE client_name ILIKE '%fort%sask%'
           OR client_name ILIKE '%exxon%'
           OR client_name ILIKE '%meyers%'
           OR display_name ILIKE '%fort%sask%'
           OR display_name ILIKE '%exxon%'
           OR display_name ILIKE '%meyers%'
           OR company_name ILIKE '%fort%sask%'
           OR company_name ILIKE '%exxon%'
           OR company_name ILIKE '%meyers%'
        ORDER BY client_name
    """)
    
    clients = cur.fetchall()
    if clients:
        print("\nFound in clients table:")
        for row in clients:
            print(f"  ID {row[0]}: {row[1]} / {row[2]} / {row[3]}")
    else:
        print("\nNo matches in clients table")

# Let's also check what client_id 1179 is (the one currently assigned)
print("\n" + "="*80)
print("CURRENT ASSIGNMENT CHECK")
print("="*80)

cur.execute("""
    SELECT client_id, client_display_name, COUNT(*) as charter_count
    FROM charters
    WHERE client_id = 1179
    GROUP BY client_id, client_display_name
""")

current = cur.fetchone()
if current:
    print(f"\nClient ID 1179 (current assignment): {current[1]} ({current[2]} charters)")

cur.close()
conn.close()

print("\n" + "="*80)
print("Once we find the correct client IDs, we can update the charters with:")
print("UPDATE charters SET client_id = [correct_id] WHERE reserve_number = '005969'")
print("="*80)
