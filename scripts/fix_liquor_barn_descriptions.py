import psycopg2
import re
import sys

# Add --write flag to actually apply changes
DRY_RUN = '--write' not in sys.argv

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REDACTED***",
    host="localhost"
)
cur = conn.cursor()

print("=" * 80)
if DRY_RUN:
    print("DRY RUN - Fix Liquor Barn Descriptions")
    print("Add --write flag to apply changes")
else:
    print("LIVE RUN - Fix Liquor Barn Descriptions")
print("=" * 80)

# Find all transactions with Liquor Barn pattern
cur.execute("""
    SELECT transaction_id, description
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND (
        description LIKE '%LB 67TH%'
        OR description LIKE '%LD NORTH%'
        OR description LIKE '%604 - LB%'
        OR description LIKE '%606 - LD%'
        OR description = '67TH ST.'
        OR description = '67TH ST'
        OR description = 'NORTH HILL'
        OR description LIKE '67TH ST. RED D%'
        OR description LIKE 'NORTH HILL RED D%'
    )
    ORDER BY transaction_date, transaction_id
""")

transactions = cur.fetchall()
print(f"\nFound {len(transactions):,} Liquor Barn transactions")

updates = []

for txn_id, old_desc in transactions:
    new_desc = old_desc
    
    # Fix 604 - LB 67TH ST. pattern -> Liquor Barn 67th St
    new_desc = re.sub(r'604\s*-\s*LB\s+67TH\s+ST\.?', 'Liquor Barn 67th St', new_desc, flags=re.IGNORECASE)
    
    # Fix 606 - LD NORTH HILL pattern -> Liquor Barn North Hill
    new_desc = re.sub(r'606\s*-\s*LD\s+NORTH\s+HILL', 'Liquor Barn North Hill', new_desc, flags=re.IGNORECASE)
    
    # Fix standalone LB 67TH ST. -> Liquor Barn 67th St
    new_desc = re.sub(r'\bLB\s+67TH\s+ST\.?', 'Liquor Barn 67th St', new_desc, flags=re.IGNORECASE)
    
    # Fix standalone LD NORTH HILL -> Liquor Barn North Hill
    new_desc = re.sub(r'\bLD\s+NORTH\s+HILL', 'Liquor Barn North Hill', new_desc, flags=re.IGNORECASE)
    
    # Fix if it was already truncated to just the street name
    if new_desc in ['67TH ST.', '67TH ST', 'NORTH HILL']:
        if '67TH' in new_desc.upper():
            new_desc = 'Liquor Barn 67th St'
        else:
            new_desc = 'Liquor Barn North Hill'
    
    if new_desc != old_desc:
        updates.append({
            'txn_id': txn_id,
            'old': old_desc,
            'new': new_desc
        })

print(f"\nTransactions to update: {len(updates):,}")

if updates:
    print("\nALL CHANGES:")
    print("-" * 80)
    for update in updates:
        print(f"OLD: {update['old']}")
        print(f"NEW: {update['new']}")
        print()

if not DRY_RUN and updates:
    print("=" * 80)
    print("APPLYING UPDATES TO DATABASE...")
    print("-" * 80)
    
    # Create backup first
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f"banking_transactions_liquor_barn_backup_{timestamp}"
    
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_id IN ({','.join(str(u['txn_id']) for u in updates)})
    """)
    
    print(f"✓ Backup created: {backup_table} ({len(updates):,} rows)")
    
    # Update descriptions
    update_count = 0
    for update in updates:
        cur.execute("""
            UPDATE banking_transactions
            SET description = %s
            WHERE transaction_id = %s
        """, (update['new'], update['txn_id']))
        update_count += cur.rowcount
    
    conn.commit()
    print(f"✓ Updated {update_count:,} transaction descriptions")
    print("✓ Changes committed to database")
else:
    print("\n" + "=" * 80)
    print("DRY RUN COMPLETE - No changes made")
    print("Run with --write flag to apply updates")

cur.close()
conn.close()
