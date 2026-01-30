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
    print("DRY RUN - Clean Scotia Merchant Deposit Descriptions")
    print("Add --write flag to apply changes")
else:
    print("LIVE RUN - Clean Scotia Merchant Deposit Descriptions")
print("=" * 80)

# Find merchant deposit transactions
cur.execute("""
    SELECT transaction_id, description
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND (
        description ILIKE '%MERCHANT DEPOSIT%'
        OR description ILIKE '%MCARD DEP%'
        OR description ILIKE '%VISA DEP%'
        OR description ILIKE '%DEBITCD DEP%'
    )
    ORDER BY transaction_date, transaction_id
""")

transactions = cur.fetchall()
print(f"\nFound {len(transactions):,} merchant deposit transactions to clean")

if not transactions:
    print("No transactions to update")
    cur.close()
    conn.close()
    exit(0)

updates = []

for txn_id, old_desc in transactions:
    new_desc = old_desc
    
    # Remove "MERCHANT DEPOSIT CREDIT" and the account number
    new_desc = re.sub(r'MERCHANT DEPOSIT CREDIT \d+\s*', '', new_desc, flags=re.IGNORECASE)
    
    # Remove "DEPOSIT" followed by long account numbers (0973847000019 pattern)
    new_desc = re.sub(r'DEPOSIT \d{10,}\s+', '', new_desc, flags=re.IGNORECASE)
    
    # Remove standalone transaction numbers (00001, etc.)
    new_desc = re.sub(r'\b\d{5}\b\s+', '', new_desc, flags=re.IGNORECASE)
    
    # Clean up MCARD DEP CR -> DEPOSIT MCARD
    new_desc = re.sub(r'MCARD DEP CR\s+', 'DEPOSIT MCARD', new_desc, flags=re.IGNORECASE)
    
    # Clean up VISA DEP CR -> DEPOSIT VISA
    new_desc = re.sub(r'VISA DEP CR\s+', 'DEPOSIT VISA', new_desc, flags=re.IGNORECASE)
    
    # Clean up DEBITCD DEP CR -> DEPOSIT DEBIT CD
    new_desc = re.sub(r'DEBITCD DEP CR\s+', 'DEPOSIT DEBIT CD', new_desc, flags=re.IGNORECASE)
    
    # Remove processor names like "CHASE PAYMENTECH", "MONERIS", etc.
    new_desc = re.sub(r'\s*(CHASE PAYMENTECH|MONERIS|GLOBAL PAYMENTS|FIRST DATA)\s*', '', new_desc, flags=re.IGNORECASE)
    
    # Clean up multiple spaces
    new_desc = re.sub(r'\s+', ' ', new_desc).strip()
    
    if new_desc != old_desc:
        updates.append({
            'txn_id': txn_id,
            'old': old_desc,
            'new': new_desc
        })

print(f"\nTransactions to update: {len(updates):,}")

if updates:
    print("\nSAMPLE CHANGES (First 20):")
    print("-" * 80)
    for update in updates[:20]:
        print(f"OLD: {update['old']}")
        print(f"NEW: {update['new']}")
        print()
    
    if len(updates) > 20:
        print(f"... ({len(updates) - 20:,} more changes)")

if not DRY_RUN and updates:
    print("\n" + "=" * 80)
    print("APPLYING UPDATES TO DATABASE...")
    print("-" * 80)
    
    # Create backup first
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f"banking_transactions_scotia_desc_backup_{timestamp}"
    
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
