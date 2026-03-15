"""
Based on LMS screenshots, reassign the 4 misassigned charters to their correct clients:
- Fort Sask Rangers
- Exxonrev  
- Meyers, Jennifer

First, let's find these clients in the database and see what charters belong to them.
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
print("SEARCHING FOR ACTUAL CLIENTS FROM SCREENSHOTS")
print("="*80)

# Search for the clients mentioned in the screenshots
clients_to_search = [
    'Fort Sask Rangers',
    'Exxonrev',
    'Meyers, Jennifer',
    'Jennifer Meyers',
    'Fort Saskatchewan Rangers'
]

print("\nSearching for clients:")
for client_name in clients_to_search:
    cur.execute("""
        SELECT DISTINCT client_id, client_display_name, COUNT(*) as charter_count
        FROM charters
        WHERE client_display_name ILIKE %s
        GROUP BY client_id, client_display_name
    """, (f'%{client_name}%',))
    
    results = cur.fetchall()
    if results:
        print(f"\n  ✓ Found '{client_name}':")
        for client_id, display_name, count in results:
            print(f"    ID {client_id}: {display_name} ({count} charters)")
    else:
        print(f"\n  ✗ Not found: '{client_name}'")

# Now let's look at charters around the same dates as our misassigned ones
print("\n" + "="*80)
print("CHARTERS NEAR MARCH 30 - APRIL 5, 2012 (excluding Perron Ventures)")
print("="*80)

cur.execute("""
    SELECT reserve_number, charter_date, client_display_name, total_amount_due
    FROM charters
    WHERE charter_date BETWEEN '2012-03-25' AND '2012-04-10'
      AND client_display_name NOT ILIKE '%Perron Ventures%'
    ORDER BY charter_date, reserve_number
""")

nearby_charters = cur.fetchall()
print(f"\nFound {len(nearby_charters)} charters:")
for reserve_num, charter_date, client_name, amount in nearby_charters[:20]:
    print(f"  {reserve_num}  {charter_date}  {client_name[:40]:<40}  ${amount:>8,.2f}")

if len(nearby_charters) > 20:
    print(f"  ... and {len(nearby_charters) - 20} more")

cur.close()
conn.close()

print("\n" + "="*80)
print("NEXT STEP:")
print("="*80)
print("""
Based on the screenshots and the search results above, we need to:
1. Identify the correct client_id for each misassigned charter
2. Update the charters table to reassign them to the correct client
3. Verify the payments are correctly attributed
""")
