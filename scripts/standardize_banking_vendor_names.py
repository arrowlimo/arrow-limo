"""
Standardize vendor names in banking transactions (no deletion)
Normalize vendor variations: Parr/Pars→Parrs, ddcentex/centis→Centex, etc.
"""
import psycopg2
import os
from datetime import datetime
import re

def normalize_vendor(vendor):
    """Normalize vendor name to standard format"""
    if not vendor:
        return None
    
    # Convert to uppercase for matching
    vendor_upper = vendor.upper()
    
    # Define standard vendor names
    standards = {
        # Gas stations
        r'CENT[EI]X|DDCENTEX|CENTIS': 'Centex',
        r'FAS\s*GAS|FASGAS': 'Fas Gas',
        r'HUSKY': 'Husky',
        r'SHELL': 'Shell',
        r'ESSO': 'Esso',
        r'PETRO\s*CAN': 'Petro-Canada',
        r'CO-?OP': 'Co-op',
        
        # Automotive
        r'PARR?S?\b': 'Parrs Automotive',
        r'CANADIAN\s*T?IRE': 'Canadian Tire',
        r'PRINCESS\s*AUTO': 'Princess Auto',
        
        # Liquor stores
        r'LIQUOR\s*BARN': 'Liquor Barn',
        r'GLOBAL\s*LIQUOR': 'Global Liquor Store',
        r'LIQUOR\s*DEPOT': 'Liquor Depot',
        r'PLAZA\s*LIQUOR': 'Plaza Liquor Store',
        
        # Restaurants
        r'TIM\s*HORT?ONS?': 'Tim Hortons',
        r'PHILS?\s*RESTAURANT': "Phil's Restaurant",
        r'FIVE\s*GUYS': 'Five Guys Burgers & Fries',
        r'TONY\s*ROMAS?': "Tony Romas",
        
        # Finance/leasing
        r'HEFFNER|HEFNER': 'Heffner Auto Finance',
        r'FIBRENEW|FIBRE\s*NEW': 'Fibrenew',
        
        # Insurance
        r'COOPERATORS': 'Cooperators',
        r'DRAYDEN\s*INSURANCE': 'Drayden Insurance',
        
        # Others
        r'WALMART': 'Walmart',
        r'SHOPPERS\s*DRUG': 'Shoppers Drug Mart',
        r'STAPLES': 'Staples',
    }
    
    # Apply standardization
    for pattern, standard in standards.items():
        if re.search(pattern, vendor_upper):
            return standard
    
    # Return original if no match (preserve original case)
    return vendor

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password=os.getenv('DB_PASSWORD')
)
cur = conn.cursor()

print("=== VENDOR NAME STANDARDIZATION (Banking Transactions) ===\n")

# Step 1: Create backup
backup_table = f"banking_transactions_vendor_std_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
print(f"Creating backup: {backup_table}...")

cur.execute(f"""
    CREATE TABLE {backup_table} AS
    SELECT * FROM banking_transactions
    WHERE account_number = '0228362'
""")
conn.commit()

cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
backup_count = cur.fetchone()[0]
print(f"✓ Backed up {backup_count:,} CIBC transactions\n")

# Step 2: Load all transactions with vendor_extracted
print("Loading transactions with vendor names...")

cur.execute("""
    SELECT 
        transaction_id,
        description,
        vendor_extracted
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND vendor_extracted IS NOT NULL
    AND vendor_extracted != ''
    ORDER BY transaction_id
""")

transactions = cur.fetchall()
print(f"Loaded {len(transactions):,} transactions with vendors\n")

# Step 3: Analyze and standardize
updates = []
vendor_changes = {}

for tid, desc, vendor in transactions:
    standardized = normalize_vendor(vendor)
    
    if standardized and standardized != vendor:
        updates.append((standardized, tid))
        
        # Track changes for reporting
        key = f"{vendor} → {standardized}"
        if key not in vendor_changes:
            vendor_changes[key] = []
        vendor_changes[key].append(tid)

print(f"=== STANDARDIZATION PREVIEW ===\n")
print(f"Total vendor names: {len(transactions):,}")
print(f"Names to standardize: {len(updates):,}")
print(f"Unique transformations: {len(vendor_changes)}\n")

# Show top transformations
print("=== TOP VENDOR NAME CHANGES ===\n")
sorted_changes = sorted(vendor_changes.items(), key=lambda x: len(x[1]), reverse=True)

for i, (change, tids) in enumerate(sorted_changes[:25], 1):
    print(f"{i:2}. {change:<60} ({len(tids):>4} transactions)")

if not updates:
    print("\n✓ All vendor names already standardized!")
    cur.close()
    conn.close()
    exit()

# Step 4: Apply updates
print(f"\n\nApplying {len(updates):,} vendor name standardizations...")

batch_size = 100
updated_total = 0

for i in range(0, len(updates), batch_size):
    batch = updates[i:i+batch_size]
    
    # Use unnest to update multiple rows efficiently
    cur.execute("""
        UPDATE banking_transactions AS bt
        SET vendor_extracted = data.new_vendor
        FROM (
            SELECT 
                unnest(%s::integer[]) as tid,
                unnest(%s::text[]) as new_vendor
        ) AS data
        WHERE bt.transaction_id = data.tid
    """, (
        [u[1] for u in batch],  # transaction_ids
        [u[0] for u in batch]   # new vendor names
    ))
    
    updated_total += cur.rowcount
    
    if (i + batch_size) % 500 == 0:
        print(f"  Updated {updated_total}/{len(updates)}...")

conn.commit()
print(f"✓ Updated {updated_total} vendor names\n")

# Step 5: Verify and report
print("=== FINAL SUMMARY ===")
print(f"Backup table: {backup_table}")
print(f"Transactions updated: {updated_total:,}")
print(f"Unique transformations: {len(vendor_changes)}")

# Show sample of each standardized vendor
print("\n=== SAMPLE STANDARDIZED VENDORS ===\n")

cur.execute("""
    SELECT DISTINCT vendor_extracted, COUNT(*) as count
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND vendor_extracted IN (
        'Centex', 'Fas Gas', 'Parrs Automotive', 'Liquor Barn',
        'Tim Hortons', 'Canadian Tire', 'Heffner Auto Finance',
        'Fibrenew', 'Phil''s Restaurant', 'Walmart', 'Husky'
    )
    GROUP BY vendor_extracted
    ORDER BY count DESC
""")

standardized = cur.fetchall()
for vendor, count in standardized:
    print(f"  {vendor:<30} {count:>4} transactions")

cur.close()
conn.close()
