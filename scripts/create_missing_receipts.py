#!/usr/bin/env python
"""
Create receipts for all missing banking transactions.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import hashlib
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password=os.environ.get('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=" * 100)
print("CREATING RECEIPTS FOR ALL MISSING BANKING TRANSACTIONS")
print("=" * 100)

# Create backup of current receipts
backup_table = f"receipts_missing_creation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM receipts")
conn.commit()
print(f"\n✓ Backup created: {backup_table}")

# Get all missing banking transactions
cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.vendor_extracted,
        bt.description,
        bt.debit_amount,
        bt.account_number
    FROM banking_transactions bt
    WHERE bt.account_number = '0228362'
    AND bt.debit_amount > 0
    AND bt.receipt_id IS NULL
    ORDER BY bt.debit_amount DESC
""")

missing_txns = cur.fetchall()
print(f"\nFound {len(missing_txns):,} missing banking transactions")

# GL code mapping for auto-categorization
GL_AUTO_MAP = {
    'fuel': '5110',
    'centex': '5110',
    'shell': '5110',
    'husky': '5110',
    'esso': '5110',
    'fas gas': '5110',
    'domo': '5110',
    'maintenance': '5120',
    'auto': '5120',
    'repair': '5120',
    'tire': '5120',
    'heffner': '5120',
    'canadian tire': '5120',
    'office': '5300',
    'staples': '5300',
    'supplies': '5300',
    'rent': '5410',
    'fibrenew': '5410',
    'insurance': '5620',
    'jevco': '5620',
    'wcb': '5630',
    'meal': '5810',
    'restaurant': '5810',
    'food': '5810',
    'tim hortons': '5810',
    'cafe': '5810',
    'liquor': '5850',
    'costco': '5920',  # Personal
}

def get_gl_code(vendor_name, description):
    """Determine GL code based on vendor/description."""
    search_text = (vendor_name or '') + ' ' + (description or '')
    search_text = search_text.lower()
    
    for keyword, gl_code in GL_AUTO_MAP.items():
        if keyword in search_text:
            return gl_code
    
    return '5850'  # Default to General Business Expense

# Track statistics
created_count = 0
skipped_count = 0
gl_distribution = {}

print(f"\nCreating receipts from banking transactions...\n")

for i, txn in enumerate(missing_txns, 1):
    vendor = txn['vendor_extracted'] or 'Banking Transaction'
    
    # Generate source hash for deduplication
    hash_input = f"{txn['transaction_date']}|{vendor}|{txn['debit_amount']:.2f}".encode('utf-8')
    source_hash = hashlib.sha256(hash_input).hexdigest()
    
    # Check if receipt already exists with this hash
    cur.execute(
        "SELECT receipt_id FROM receipts WHERE source_hash = %s",
        (source_hash,)
    )
    if cur.fetchone():
        skipped_count += 1
        continue
    
    # Calculate GST (5% included in amount)
    debit_float = float(txn['debit_amount'])
    gst_amount = debit_float * 0.05 / 1.05
    net_amount = debit_float - gst_amount
    
    # Determine GL code
    gl_code = get_gl_code(vendor, txn['description'])
    
    # Get GL name
    gl_names = {
        '5110': 'Fuel & Gas',
        '5120': 'Vehicle Maintenance & Repair',
        '5300': 'Office Equipment & Supplies',
        '5410': 'Rent',
        '5620': 'Insurance',
        '5630': 'WCB',
        '5810': 'Meals & Entertainment',
        '5850': 'General Business Expense',
        '5920': 'Personal Shopping',
    }
    gl_name = gl_names.get(gl_code, 'General Business Expense')
    
    # Track GL distribution
    gl_distribution[gl_code] = gl_distribution.get(gl_code, 0) + 1
    
    # Insert receipt
    try:
        cur.execute("""
            INSERT INTO receipts (
                receipt_date,
                vendor_name,
                gross_amount,
                gst_amount,
                net_amount,
                description,
                currency,
                created_from_banking,
                banking_transaction_id,
                mapped_bank_account_id,
                source_hash,
                gl_account_code,
                gl_account_name,
                validation_status,
                source_system,
                source_reference
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING receipt_id
        """, (
            txn['transaction_date'],
            vendor,
            round(txn['debit_amount'], 2),
            round(gst_amount, 2),
            round(net_amount, 2),
            txn['description'],
            'CAD',
            True,
            txn['transaction_id'],
            1,  # CIBC account
            source_hash,
            gl_code,
            gl_name,
            'BANKING_IMPORT',
            'BANKING_IMPORT',
            f"BT:{txn['transaction_id']}"
        ))
        
        receipt_id = cur.fetchone()['receipt_id']
        
        # Update banking_transactions with receipt_id
        cur.execute(
            "UPDATE banking_transactions SET receipt_id = %s WHERE transaction_id = %s",
            (receipt_id, txn['transaction_id'])
        )
        
        created_count += 1
        
        if i % 100 == 0:
            print(f"  Created {i:,} receipts...")
    
    except Exception as e:
        print(f"  Error creating receipt for {vendor}: {e}")
        continue

conn.commit()

print(f"\n" + "=" * 100)
print("RESULTS")
print("=" * 100)
print(f"\n✓ Created: {created_count:,} receipts")
print(f"✓ Skipped: {skipped_count:,} (already exist)")
print(f"✓ Total: {created_count + skipped_count:,}")

print(f"\nGL Code Distribution:")
for gl_code in sorted(gl_distribution.keys()):
    count = gl_distribution[gl_code]
    print(f"  {gl_code}: {count:,} receipts")

# Verify totals
print(f"\n" + "=" * 100)
print("VERIFICATION")
print("=" * 100)

cur.execute("""
    SELECT 
        COUNT(*) as total_receipts,
        COUNT(CASE WHEN created_from_banking = TRUE THEN 1 END) as from_banking,
        ROUND(SUM(gross_amount)::numeric, 2) as total_amount
    FROM receipts
""")

stats = cur.fetchone()
print(f"\nReceipt Table Stats:")
print(f"  Total receipts: {stats['total_receipts']:,}")
print(f"  From banking: {stats['from_banking']:,}")
print(f"  Total amount: ${stats['total_amount']:,.2f}")

cur.execute("""
    SELECT 
        COUNT(*) as total_debits,
        COUNT(CASE WHEN receipt_id IS NOT NULL THEN 1 END) as with_receipt,
        COUNT(CASE WHEN receipt_id IS NULL THEN 1 END) as without_receipt,
        ROUND(SUM(debit_amount)::numeric, 2) as total_debits_amount
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND debit_amount > 0
""")

bank_stats = cur.fetchone()
print(f"\nBanking Debit Stats (After Receipt Creation):")
print(f"  Total debits: {bank_stats['total_debits']:,}")
print(f"  With receipt: {bank_stats['with_receipt']:,} ({100*bank_stats['with_receipt']/bank_stats['total_debits']:.1f}%)")
print(f"  Without receipt: {bank_stats['without_receipt']:,} ({100*bank_stats['without_receipt']/bank_stats['total_debits']:.1f}%)")
print(f"  Total amount: ${bank_stats['total_debits_amount']:,.2f}")

print("\n" + "=" * 100)
print("✓ RECEIPT CREATION COMPLETE")
print("=" * 100 + "\n")

conn.close()
