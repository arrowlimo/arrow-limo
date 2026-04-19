"""Fix sequence and create clients"""
import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='ArrowLimousine'
)
cur = conn.cursor()

# Fix the sequence
cur.execute("SELECT MAX(client_id) FROM clients")
max_id = cur.fetchone()[0]
cur.execute(f"SELECT setval('clients_client_id_seq', {max_id + 1})")
print(f"✓ Reset sequence to {max_id + 1}")

# Get next account number
cur.execute("""
    SELECT COALESCE(MAX(CAST(account_number AS INTEGER)), 0) + 1
    FROM clients
    WHERE account_number ~ '^[0-9]+$'
""")
next_account = cur.fetchone()[0]

# Create Fort Sask Rangers
cur.execute("SELECT client_id FROM clients WHERE client_name = 'Fort Sask Rangers'")
if not cur.fetchone():
    cur.execute("""
        INSERT INTO clients (account_number, client_name, company_name, created_at, updated_at, is_active)
        VALUES (%s, %s, %s, %s, %s, true)
        RETURNING client_id
    """, (str(next_account), 'Fort Sask Rangers', 'Fort Sask Rangers', datetime.now(), datetime.now()))
    fort_sask_id = cur.fetchone()[0]
    print(f"✓ Created Fort Sask Rangers: ID {fort_sask_id}")
    next_account += 1
else:
    cur.execute("SELECT client_id FROM clients WHERE client_name = 'Fort Sask Rangers'")
    fort_sask_id = cur.fetchone()[0]
    print(f"✓ Found Fort Sask Rangers: ID {fort_sask_id}")

# Create Fibrenew
cur.execute("SELECT client_id FROM clients WHERE client_name = 'Fibrenew'")
if not cur.fetchone():
    cur.execute("""
        INSERT INTO clients (account_number, client_name, company_name, created_at, updated_at, is_active)
        VALUES (%s, %s, %s, %s, %s, true)
        RETURNING client_id
    """, (str(next_account), 'Fibrenew', 'Fibrenew', datetime.now(), datetime.now()))
    fibrenew_id = cur.fetchone()[0]
    print(f"✓ Created Fibrenew: ID {fibrenew_id}")
else:
    cur.execute("SELECT client_id FROM clients WHERE client_name = 'Fibrenew'")
    fibrenew_id = cur.fetchone()[0]
    print(f"✓ Found Fibrenew: ID {fibrenew_id}")

# Update charters
updates = [
    ('005969', 4533, 'Meyn, Jennifer L'),
    ('005970', fort_sask_id, 'Fort Sask Rangers'),
    ('005971', fibrenew_id, 'Fibrenew'),
    ('006026', fort_sask_id, 'Fort Sask Rangers')
]

print("\nUpdating charters:")
for reserve_num, client_id, client_name in updates:
    cur.execute("UPDATE charters SET client_id = %s, client_display_name = %s WHERE reserve_number = %s",
                (client_id, client_name, reserve_num))
    print(f"  {reserve_num} → {client_name} (ID {client_id})")

conn.commit()
conn.close()
print("\n✅ Done!")
