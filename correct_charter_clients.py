"""
Create missing client records and update charters with correct client_id values
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
print("CORRECTING CLIENT ASSIGNMENTS")
print("="*80)

# Get next available account number
cur.execute("""
    SELECT COALESCE(MAX(CAST(account_number AS INTEGER)), 0) + 1
    FROM clients
    WHERE account_number ~ '^[0-9]+$'
""")
next_account = cur.fetchone()[0]
print(f"\nNext available account number: {next_account}")

# Step 1: Create Fort Sask Rangers client if it doesn't exist
print("\n1. Creating Fort Sask Rangers client...")
cur.execute("""
    INSERT INTO clients (
        client_name, company_name, account_number, created_at, updated_at, is_active
    ) VALUES (
        'Fort Sask Rangers', 'Fort Sask Rangers', %s, %s, %s, true
    )
    ON CONFLICT DO NOTHING
    RETURNING client_id
""", (str(next_account), datetime.now(), datetime.now()))

result = cur.fetchone()
if result:
    fort_sask_id = result[0]
    print(f"   ✓ Created client ID {fort_sask_id}")
else:
    # Already exists, find it
    cur.execute("SELECT client_id FROM clients WHERE client_name = 'Fort Sask Rangers'")
    result = cur.fetchone()
    if result:
        fort_sask_id = result[0]
        print(f"   ✓ Found existing client ID {fort_sask_id}")
    else:
        print("   ✗ Failed to create Fort Sask Rangers")
        fort_sask_id = None

# Step 2: Create Fibrenew client if it doesn't exist
print("\n2. Creating Fibrenew client...")
cur.execute("""
    INSERT INTO clients (
        client_name, company_name, account_number, created_at, updated_at, is_active
    ) VALUES (
        'Fibrenew', 'Fibrenew', %s, %s, %s, true
    )
    ON CONFLICT DO NOTHING
    RETURNING client_id
""", (str(next_account + 1), datetime.now(), datetime.now()))

result = cur.fetchone()
if result:
    fibrenew_id = result[0]
    print(f"   ✓ Created client ID {fibrenew_id}")
else:
    # Already exists, find it
    cur.execute("SELECT client_id FROM clients WHERE client_name = 'Fibrenew'")
    result = cur.fetchone()
    if result:
        fibrenew_id = result[0]
        print(f"   ✓ Found existing client ID {fibrenew_id}")
    else:
        print("   ✗ Failed to create Fibrenew")
        fibrenew_id = None

# Step 3: Update charters with correct client_id
print("\n" + "="*80)
print("UPDATING CHARTER CLIENT ASSIGNMENTS")
print("="*80)

updates = [
    ('005969', 4533, 'Meyn, Jennifer'),
    ('005970', fort_sask_id, 'Fort Sask Rangers'),
    ('005971', fibrenew_id, 'Fibrenew'),
    ('006026', fort_sask_id, 'Fort Sask Rangers')
]

for reserve_num, client_id, client_name in updates:
    if client_id:
        # Get current assignment
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
            
            # Update charter
            cur.execute("""
                UPDATE charters
                SET client_id = %s,
                    client_display_name = %s
                WHERE reserve_number = %s
            """, (client_id, client_name, reserve_num))
            
            print(f"   ✓ Updated")
        else:
            print(f"\n{reserve_num}: NOT FOUND in charters table")
    else:
        print(f"\n{reserve_num}: Skipping (no valid client_id)")

# Commit changes
conn.commit()

print("\n" + "="*80)
print("VERIFICATION")
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
print("✅ COMPLETE - Charters reassigned to correct clients")
print("="*80)
