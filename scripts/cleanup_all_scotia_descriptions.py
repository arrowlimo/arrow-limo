import psycopg2
import re
import sys

# Add --write flag to actually apply changes
DRY_RUN = '--write' not in sys.argv

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REMOVED***",
    host="localhost"
)
cur = conn.cursor()

print("=" * 80)
if DRY_RUN:
    print("DRY RUN - Comprehensive Scotia Description Cleanup")
    print("Add --write flag to apply changes")
else:
    print("LIVE RUN - Comprehensive Scotia Description Cleanup")
print("=" * 80)

# Get all Scotia transactions
cur.execute("""
    SELECT transaction_id, description
    FROM banking_transactions
    WHERE account_number = '903990106011'
    ORDER BY transaction_date, transaction_id
""")

transactions = cur.fetchall()
print(f"\nAnalyzing {len(transactions):,} Scotia transactions...")

updates = []

for txn_id, old_desc in transactions:
    new_desc = old_desc
    
    # Remove "POINT OF SALE PURCHASE" prefix
    new_desc = re.sub(r'^POINT OF SALE PURCHASE\s+', '', new_desc, flags=re.IGNORECASE)
    
    # Remove "POS Purchase" prefix
    new_desc = re.sub(r'^POS Purchase\s+', '', new_desc, flags=re.IGNORECASE)
    
    # Remove city and province suffixes (RED DEER AB, RED DEER ABCA, RED DEER ABCD, EDMONTON ABCA, etc.)
    new_desc = re.sub(r'\s+(RED DEER|EDMONTON|CALGARY|LETHBRIDGE)\s+AB[A-Z]*$', '', new_desc, flags=re.IGNORECASE)
    
    # Remove "Miscellaneous Payment" prefix
    new_desc = re.sub(r'^Miscellaneous Payment\s+', '', new_desc, flags=re.IGNORECASE)
    
    # Remove "MISC PAYMENT" prefix
    new_desc = re.sub(r'^MISC PAYMENT\s+', '', new_desc, flags=re.IGNORECASE)
    
    # Simplify ABM WITHDRAWAL
    new_desc = re.sub(r'^ABM WITHDRAWAL\s+.*?(RED DEER|GAETZ)', 'ATM Withdrawal', new_desc, flags=re.IGNORECASE)
    
    # Remove card numbers (4506*********359 pattern)
    new_desc = re.sub(r'\s*\d{4}\*+\d{3,4}\s*', ' ', new_desc, flags=re.IGNORECASE)
    
    # Remove [QB: -SPLIT-] prefix
    new_desc = re.sub(r'^\[QB:\s*-SPLIT-\]\s+', '', new_desc, flags=re.IGNORECASE)
    
    # Remove QuickBooks item references like [QB: 16571]
    new_desc = re.sub(r'\[QB:\s*\d+\]\s*', '', new_desc, flags=re.IGNORECASE)
    
    # Shorten "Bill Pmt-Cheque dd" to "Bill Payment"
    new_desc = re.sub(r'Bill Pmt-Cheque dd\s+', 'Bill Payment ', new_desc, flags=re.IGNORECASE)
    new_desc = re.sub(r'Bill Pmt-Cheque\s+\d+\s+', 'Bill Payment ', new_desc, flags=re.IGNORECASE)
    
    # Remove location codes from gas stations (604 - LB, 606 - LD, etc.)
    new_desc = re.sub(r'\d{3}\s*-\s*[A-Z]{2}\s+', '', new_desc, flags=re.IGNORECASE)
    
    # Remove store/location codes in parentheses at start
    new_desc = re.sub(r'^\d{3,5}\s+', '', new_desc)
    
    # Remove cryptic location codes like 50AVQPE, 30AVIQFE, #1205, #4320
    new_desc = re.sub(r'\s+\d{2}AV[IQ]*[A-Z]+', '', new_desc, flags=re.IGNORECASE)
    new_desc = re.sub(r'\s+#\d+', '', new_desc)
    
    # Remove (C-STOR) designation
    new_desc = re.sub(r'\s*\(C-STOR[Y]?\)', '', new_desc, flags=re.IGNORECASE)
    
    # Remove INTERAC designation
    new_desc = re.sub(r'\s+INTERAC\s*', ' ', new_desc, flags=re.IGNORECASE)
    
    # Remove QPS, QPE, Q2P designations
    new_desc = re.sub(r'\s+Q[P0-9]{2}\s*', ' ', new_desc, flags=re.IGNORECASE)
    
    # Remove "AMEX BANK OF CANADA" suffix
    new_desc = re.sub(r'\s+AMEX BANK OF CANADA$', '', new_desc, flags=re.IGNORECASE)
    
    # Remove AMEX transaction numbers
    new_desc = re.sub(r'\s+AMEX\s+\d+', ' AMEX', new_desc, flags=re.IGNORECASE)
    
    # Simplify RENT/LEASES transactions
    new_desc = re.sub(r'^RENT/LEASES\s+[A-Z0-9]+<[^>]+>\s+', 'Rent/Lease ', new_desc, flags=re.IGNORECASE)
    
    # Remove DEBIT MEMO prefix
    new_desc = re.sub(r'^DEBIT MEMO\s+', '', new_desc, flags=re.IGNORECASE)
    
    # Remove "Debit Memo" prefix
    new_desc = re.sub(r'^Debit Memo\s+', '', new_desc, flags=re.IGNORECASE)
    
    # Simplify RETURNED NSF CHEQUE
    new_desc = re.sub(r'^RETURNED ITEM/CHARGEBACK.*?RETURNED NSF CHEQUE', 'NSF Cheque Returned', new_desc, flags=re.IGNORECASE)
    new_desc = re.sub(r'^RETURNED NSF CHEQUE\s+\d*', 'NSF Cheque Returned', new_desc, flags=re.IGNORECASE)
    
    # Clean up CENTEX variations
    new_desc = re.sub(r'CENTEX DEERPARK?\s*', 'Centex ', new_desc, flags=re.IGNORECASE)
    new_desc = re.sub(r'CENTEX DEERPAK\s*', 'Centex ', new_desc, flags=re.IGNORECASE)
    
    # Clean up multiple spaces
    new_desc = re.sub(r'\s+', ' ', new_desc).strip()
    
    # Remove trailing ellipsis or dots
    new_desc = re.sub(r'\.{3,}$', '', new_desc).strip()
    
    if new_desc != old_desc:
        updates.append({
            'txn_id': txn_id,
            'old': old_desc,
            'new': new_desc
        })

print(f"\nTransactions to update: {len(updates):,}")

if updates:
    print("\nSAMPLE CHANGES (First 30):")
    print("-" * 80)
    for update in updates[:30]:
        print(f"OLD: {update['old']}")
        print(f"NEW: {update['new']}")
        print()
    
    if len(updates) > 30:
        print(f"... ({len(updates) - 30:,} more changes)")

if not DRY_RUN and updates:
    print("\n" + "=" * 80)
    print("APPLYING UPDATES TO DATABASE...")
    print("-" * 80)
    
    # Create backup first
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f"banking_transactions_scotia_cleanup_backup_{timestamp}"
    
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
