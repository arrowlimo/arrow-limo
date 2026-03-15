"""
Find the correct client IDs for the charters shown in screenshots
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
print("SEARCHING FOR CLIENT IDs")
print("="*80)

# First check the structure of clients table
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'clients'
    ORDER BY ordinal_position
""")
print("\nClients table columns:")
for col_name, col_type in cur.fetchall():
    print(f"  {col_name}: {col_type}")

print("\n" + "="*80)
print("SEARCHING FOR: Fort Sask Rangers")
print("="*80)

cur.execute("""
    SELECT client_id, client_name
    FROM clients
    WHERE client_name ILIKE '%fort%sask%'
       OR client_name ILIKE '%rangers%'
    LIMIT 20
""")
results = cur.fetchall()
if results:
    for client_id, name in results:
        print(f"  ID {client_id}: {name}")
else:
    print("  Not found")

print("\n" + "="*80)
print("SEARCHING FOR: Exxonrev")
print("="*80)

cur.execute("""
    SELECT client_id, client_name
    FROM clients
    WHERE client_name ILIKE '%exxon%'
       OR client_name ILIKE '%exon%'
    LIMIT 20
""")
results = cur.fetchall()
if results:
    for client_id, name in results:
        print(f"  ID {client_id}: {name}")
else:
    print("  Not found")

print("\n" + "="*80)
print("SEARCHING FOR: Meyers, Jennifer")
print("="*80)

cur.execute("""
    SELECT client_id, client_name
    FROM clients
    WHERE client_name ILIKE '%meyers%jennifer%'
       OR client_name ILIKE '%jennifer%meyers%'
    LIMIT 20
""")
results = cur.fetchall()
if results:
    for client_id, name in results:
        print(f"  ID {client_id}: {name}")
else:
    print("  Not found - searching for just 'Meyers':")
    cur.execute("""
        SELECT client_id, client_name
        FROM clients
        WHERE client_name ILIKE '%meyers%'
        LIMIT 20
    """)
    results = cur.fetchall()
    for client_id, name in results:
        print(f"  ID {client_id}: {name}")

# Now let's look at charters 005969, 005970, 005971, 006026 to see if there are any clues
print("\n" + "="*80)
print("CHECKING CHARTER DETAILS FOR CLUES")
print("="*80)

for reserve_num in ['005969', '005970', '005971', '006026']:
    cur.execute("""
        SELECT reserve_number, charter_date, client_display_name, total_amount_due,
               client_notes, booking_notes
        FROM charters
        WHERE reserve_number = %s
    """, (reserve_num,))
    
    row = cur.fetchone()
    if row:
        print(f"\n{row[0]} ({row[1]}) - ${row[3]:,.2f}:")
        print(f"  Current Client: {row[2]}")
        if row[4]:
            print(f"  Client Notes: {row[4][:150]}")
        if row[5]:
            print(f"  Booking Notes: {row[5][:150]}")

cur.close()
conn.close()
