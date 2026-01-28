"""
Find and delete duplicate banking transactions using fuzzy vendor matching
Group by: exact date + exact amount + fuzzy vendor name
"""
import psycopg2
import os
from datetime import datetime
import re

def normalize_vendor(vendor):
    """Normalize vendor name for fuzzy matching"""
    if not vendor:
        return ""
    
    # Convert to uppercase
    vendor = vendor.upper()
    
    # Remove common prefixes/suffixes
    vendor = re.sub(r'\b(CHEQUE|CHQ|PURCHASE|DEBIT|CREDIT)\b', '', vendor)
    vendor = re.sub(r'#?\d+', '', vendor)  # Remove numbers
    
    # Remove special characters
    vendor = re.sub(r'[^\w\s]', '', vendor)
    
    # Normalize common vendor variations
    replacements = {
        r'PARR?S?\b': 'PARRS',
        r'CENT[EI]X|DDCENTEX': 'CENTEX',
        r'FAS\s*GAS|FASGAS': 'FASGAS',
        r'LIQUOR\s*BARN|LIQ\s*BARN': 'LIQUORBARN',
        r'GLOBAL\s*LIQUOR': 'GLOBALLIQUOR',
        r'CANADIAN\s*TIRE': 'CANADIANTIRE',
        r'TIM\s*HORT?ON': 'TIMHORTONS',
        r'HEFFNER|HEFNER': 'HEFFNER',
        r'FIBRENEW|FIBRE\s*NEW': 'FIBRENEW',
    }
    
    for pattern, replacement in replacements.items():
        vendor = re.sub(pattern, replacement, vendor)
    
    # Collapse whitespace
    vendor = re.sub(r'\s+', '', vendor)
    
    return vendor.strip()

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password=os.getenv('DB_PASSWORD')
)
cur = conn.cursor()

print("=== FUZZY VENDOR DUPLICATE DETECTION ===\n")

# Step 1: Create backup
backup_table = f"banking_transactions_fuzzy_dedup_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
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

# Step 2: Get all transactions and group by fuzzy vendor
print("Loading transactions and normalizing vendor names...")

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        vendor_extracted,
        COALESCE(debit_amount, 0) as debit,
        COALESCE(credit_amount, 0) as credit
    FROM banking_transactions
    WHERE account_number = '0228362'
    ORDER BY transaction_date, transaction_id
""")

transactions = cur.fetchall()
print(f"Loaded {len(transactions):,} transactions\n")

# Group by date + amount + normalized vendor
groups = {}
for txn in transactions:
    tid, date, desc, vendor, debit, credit = txn
    
    # Extract vendor from description if vendor_extracted is null
    vendor_text = vendor if vendor else desc
    normalized = normalize_vendor(vendor_text)
    
    # Create composite key
    key = (date, debit, credit, normalized)
    
    if key not in groups:
        groups[key] = []
    groups[key].append({
        'id': tid,
        'date': date,
        'desc': desc,
        'vendor': vendor,
        'debit': debit,
        'credit': credit
    })

# Find duplicate groups
duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}

print(f"Found {len(duplicate_groups)} fuzzy duplicate groups\n")

if not duplicate_groups:
    print("✓ No fuzzy duplicates found!")
    cur.close()
    conn.close()
    exit()

# Step 3: Preview top duplicates
print("=== TOP 20 FUZZY DUPLICATE GROUPS ===\n")

sorted_groups = sorted(duplicate_groups.items(), key=lambda x: len(x[1]), reverse=True)

for i, (key, txns) in enumerate(sorted_groups[:20], 1):
    date, debit, credit, norm_vendor = key
    amount = debit if debit > 0 else credit
    
    print(f"{i}. {date} | ${amount:,.2f} | {len(txns)} copies | Normalized: '{norm_vendor}'")
    
    for txn in txns:
        print(f"   TX {txn['id']}: {txn['desc'][:60]}")
        if txn['vendor']:
            print(f"              Vendor: {txn['vendor']}")
    print()

# Step 4: Build deletion list (keep oldest transaction_id)
to_delete = []
delete_summary = []

for key, txns in duplicate_groups.items():
    # Sort by transaction_id, keep first (oldest)
    sorted_txns = sorted(txns, key=lambda x: x['id'])
    keep = sorted_txns[0]
    delete = sorted_txns[1:]
    
    to_delete.extend([t['id'] for t in delete])
    
    delete_summary.append({
        'date': key[0],
        'amount': key[1] if key[1] > 0 else key[2],
        'normalized': key[3],
        'count': len(txns),
        'keep': keep['id'],
        'delete': [t['id'] for t in delete],
        'descriptions': [t['desc'][:40] for t in txns]
    })

print(f"\n=== DELETION PLAN ===")
print(f"Duplicate groups: {len(duplicate_groups)}")
print(f"Transactions to delete: {len(to_delete)}")
print(f"Transactions to keep: {len(duplicate_groups)}")
print(f"Total duplicates affected: {len(to_delete) + len(duplicate_groups)}")

# Step 5: Ask for confirmation and execute
print(f"\n⚠️  READY TO DELETE {len(to_delete)} DUPLICATE TRANSACTIONS")
print(f"Backup: {backup_table}")

# Execute deletion
if to_delete:
    print(f"\nDeleting {len(to_delete)} fuzzy duplicate transactions...")
    
    # First, check for foreign key references
    cur.execute("""
        SELECT DISTINCT bt.transaction_id
        FROM banking_transactions bt
        WHERE bt.transaction_id = ANY(%s)
        AND EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger brml 
            WHERE brml.banking_transaction_id = bt.transaction_id
        )
    """, (to_delete,))
    
    linked_to_receipts = [row[0] for row in cur.fetchall()]
    
    cur.execute("""
        SELECT DISTINCT bt.transaction_id
        FROM banking_transactions bt
        WHERE bt.transaction_id = ANY(%s)
        AND EXISTS (
            SELECT 1 FROM etransfer_transactions et
            WHERE et.banking_transaction_id = bt.transaction_id
        )
    """, (to_delete,))
    
    linked_to_etransfer = [row[0] for row in cur.fetchall()]
    
    # Remove linked transactions from delete list
    protected = set(linked_to_receipts + linked_to_etransfer)
    safe_to_delete = [tid for tid in to_delete if tid not in protected]
    
    if protected:
        print(f"\n⚠️  Protected {len(protected)} transactions with foreign key references:")
        print(f"   - Linked to receipts: {len(linked_to_receipts)}")
        print(f"   - Linked to etransfers: {len(linked_to_etransfer)}")
        print(f"   - Safe to delete: {len(safe_to_delete)}")
    
    if not safe_to_delete:
        print("\n❌ No transactions can be safely deleted (all have foreign key references)")
        cur.close()
        conn.close()
        exit()
    
    # Delete in batches
    batch_size = 100
    deleted_total = 0
    
    for i in range(0, len(safe_to_delete), batch_size):
        batch = safe_to_delete[i:i+batch_size]
        cur.execute("""
            DELETE FROM banking_transactions
            WHERE transaction_id = ANY(%s)
        """, (batch,))
        deleted_total += cur.rowcount
        
        if (i + batch_size) % 500 == 0:
            print(f"  Deleted {deleted_total}/{len(safe_to_delete)}...")
    
    conn.commit()
    print(f"✓ Deleted {deleted_total} fuzzy duplicate transactions\n")
    
    # Step 6: Verify
    cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE account_number = '0228362'")
    final_count = cur.fetchone()[0]
    
    print("=== FINAL SUMMARY ===")
    print(f"Original transactions: {backup_count:,}")
    print(f"Fuzzy duplicates deleted: {deleted_total:,}")
    print(f"Final transactions: {final_count:,}")
    print(f"Backup table: {backup_table}")
    
    # Show some examples of cleaned vendor variations
    print("\n=== VENDOR VARIATIONS MERGED ===")
    for item in delete_summary[:10]:
        if len(set(item['descriptions'])) > 1:
            print(f"\n{item['normalized']} ({item['count']} variations):")
            for desc in set(item['descriptions']):
                print(f"  - {desc}")

cur.close()
conn.close()
