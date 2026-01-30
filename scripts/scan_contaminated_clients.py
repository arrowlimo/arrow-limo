"""
Clean up contaminated client records in the clients table.
Identifies junk data (products, gibberish, etc.) and removes them or marks as invalid.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Find contaminated client records (junk data patterns)
junk_patterns = [
    'flat', 'bud', 'light', 'beer', 'bottle',  # Products
    'email', 'test', 'sample', 'unknown',       # Junk
    'none', 'null', 'n/a',                      # Empty/invalid
]

print("🔍 Scanning for contaminated client records...\n")

cur.execute("""
    SELECT client_id, client_name, company_name, 
           (SELECT COUNT(*) FROM charters WHERE client_id = c.client_id) as charter_count
    FROM clients c
    WHERE client_name IS NOT NULL
    ORDER BY client_id
""")

junk_clients = []
for client_id, client_name, company_name, charter_count in cur.fetchall():
    name_to_check = (client_name or '').lower()
    
    # Check for junk patterns
    is_junk = False
    for pattern in junk_patterns:
        if pattern in name_to_check:
            is_junk = True
            break
    
    if is_junk:
        junk_clients.append({
            'id': client_id,
            'name': client_name,
            'company': company_name,
            'charters': charter_count
        })

print(f"Found {len(junk_clients)} contaminated client records:\n")
for rec in junk_clients:
    print(f"  ID {rec['id']}: {rec['name']} (company: {rec['company']}, charters: {rec['charters']})")

# Show which charters point to these junk clients
if junk_clients:
    print("\n📋 Charters pointing to junk clients:")
    for rec in junk_clients:
        cur.execute("""
            SELECT reserve_number, charter_date, employee_id
            FROM charters
            WHERE client_id = %s
            ORDER BY charter_date DESC
        """, (rec['id'],))
        
        charters = cur.fetchall()
        if charters:
            print(f"\n  Client ID {rec['id']} ({rec['name']}):")
            for res_num, charter_date, emp_id in charters:
                print(f"    - Reserve {res_num} ({charter_date}), employee_id: {emp_id}")

print("\n✅ Run cleanup_contaminated_clients.py to remove these records")
print("   (This will delete junk client records and set charters.client_id to NULL)\n")

cur.close()
conn.close()
