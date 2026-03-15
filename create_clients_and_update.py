"""
Create missing client records properly and update charters
"""
import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='ArrowLimousine'
)
cur = conn.cursor()

print("="*80)
print("CREATING MISSING CLIENT RECORDS")
print("="*80)

# Get next available account number
cur.execute("""
    SELECT COALESCE(MAX(CAST(account_number AS INTEGER)), 0) + 1
    FROM clients
    WHERE account_number ~ '^[0-9]+$'
""")
next_account = cur.fetchone()[0]
print(f"\nNext available account number: {next_account}")

# Client 1: Fort Sask Rangers
print("\n1. Fort Sask Rangers...")
cur.execute("SELECT client_id FROM clients WHERE client_name = 'Fort Sask Rangers'")
result = cur.fetchone()
if result:
    fort_sask_id = result[0]
    print(f"   ✓ Already exists: Client ID {fort_sask_id}")
else:
    cur.execute("""
        INSERT INTO clients (
            account_number, client_name, company_name, 
            created_at, updated_at, is_active
        ) VALUES (%s, %s, %s, %s, %s, true)
        RETURNING client_id
    """, (str(next_account), 'Fort Sask Rangers', 'Fort Sask Rangers', 
          datetime.now(), datetime.now()))
    
    fort_sask_id = cur.fetchone()[0]
    print(f"   ✓ Created: Client ID {fort_sask_id}")
    next_account += 1

# Client 2: Fibrenew
print("\n2. Fibrenew...")
cur.execute("SELECT client_id FROM clients WHERE client_name = 'Fibrenew'")
result = cur.fetchone()
if result:
    fibrenew_id = result[0]
    print(f"   ✓ Already exists: Client ID {fibrenew_id}")
else:
    cur.execute("""
        INSERT INTO clients (
            account_number, client_name, company_name,
            created_at, updated_at, is_active
        ) VALUES (%s, %s, %s, %s, %s, true)
        RETURNING client_id
    """, (str(next_account), 'Fibrenew', 'Fibrenew',
          datetime.now(), datetime.now()))
    
    fibrenew_id = cur.fetchone()[0]
    print(f"   ✓ Created: Client ID {fibrenew_id}")

conn.commit()

print("\n" + "="*80)
print("UPDATING CHARTER CLIENT ASSIGNMENTS")
print("="*80)

updates = [
    ('005969', 4533, 'Meyn, Jennifer L'),
    ('005970', fort_sask_id, 'Fort Sask Rangers'),
    ('005971', fibrenew_id, 'Fibrenew'),
    ('006026', fort_sask_id, 'Fort Sask Rangers')
]

for reserve_num, client_id, client_name in updates:
    cur.execute("""
        SELECT client_id, client_display_name
        FROM charters
        WHERE reserve_number = %s
    """, (reserve_num,))
    
    current = cur.fetchone()
    if current:
        print(f"\n{reserve_num}:")
        print(f"   Old: Client ID {current[0]} ({current[1]})")
        print(f"   New: Client ID {client_id} ({client_name})")
        
        cur.execute("""
            UPDATE charters
            SET client_id = %s,
                client_display_name = %s
            WHERE reserve_number = %s
        """, (client_id, client_name, reserve_num))
        
        print(f"   ✓ Updated")

conn.commit()

print("\n" + "="*80)
print("FINAL VERIFICATION")
print("="*80)

for reserve_num, _, _ in updates:
    cur.execute("""
        SELECT reserve_number, charter_date, client_id, client_display_name, 
               total_amount_due, balance
        FROM charters
        WHERE reserve_number = %s
    """, (reserve_num,))
    
    row = cur.fetchone()
    if row:
        print(f"\n{row[0]} ({row[1]}):")
        print(f"   Client ID:   {row[2]}")
        print(f"   Client Name: {row[3]}")
        print(f"   Amount:      ${row[4]:,.2f}")
        print(f"   Balance:     ${row[5]:,.2f}")

cur.close()
conn.close()

print("\n" + "="*80)
print("✅ COMPLETE - All charters corrected")
print("="*80)
print("\nPerron Ventures charters now correctly updated:")
print("  - 005969 → Meyn, Jennifer L")
print("  - 005970 → Fort Sask Rangers")
print("  - 005971 → Fibrenew")
print("  - 006026 → Fort Sask Rangers")
