"""
Move 2012 negative payments (business expenses) to receipts table.
- Extracts vendor from notes (QBO Import patterns)
- Categorizes by description keywords
- Creates receipts with GST calculation (5% included model)
- Marks original payments for deletion after verification
"""
import os
import psycopg2
from datetime import date, datetime
import argparse

DB = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'dbname': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '***REMOVED***'),
}

YEAR = 2012

# Category mappings from description keywords
CATEGORIES = {
    'workers comp': 'Insurance',
    'wcb': 'Insurance',
    'telus': 'Telephone',
    'phone': 'Telephone',
    'sasktel': 'Telephone',
    'debit memo': 'Bank Charges',
    'bill payment': 'Accounts Payable',
    'cheque': 'Accounts Payable',
    'fuel': 'Fuel',
    'gas': 'Fuel',
    'insurance': 'Insurance',
    'rent': 'Rent',
    'utilities': 'Utilities',
    'maintenance': 'Repairs & Maintenance',
    'repair': 'Repairs & Maintenance',
}

def extract_vendor(notes: str) -> str:
    """Extract vendor from QBO Import notes"""
    if not notes:
        return 'Unknown Vendor'
    
    # Pattern: "QBO Import: VENDOR_NAME | Description"
    if 'QBO Import:' in notes:
        parts = notes.split('QBO Import:', 1)[1].split('|', 1)
        vendor = parts[0].strip()
        # Clean up common prefixes
        vendor = vendor.replace('PC-', '').replace('BR ', '').strip()
        return vendor if vendor else 'Unknown Vendor'
    
    return 'Unknown Vendor'

def categorize(vendor: str, notes: str) -> str:
    """Categorize expense by vendor/description keywords"""
    text = (vendor + ' ' + (notes or '')).lower()
    
    for keyword, category in CATEGORIES.items():
        if keyword in text:
            return category
    
    return 'General Expense'

def calculate_gst(gross_amount) -> tuple:
    """Calculate GST included (5% Alberta model)"""
    gross = float(gross_amount)
    gst = round(gross * 0.05 / 1.05, 2)
    net = round(gross - gst, 2)
    return gst, net

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Actually migrate')
    args = parser.parse_args()
    
    s, e = date(YEAR, 1, 1), date(YEAR + 1, 1, 1)
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    
    # Get negative payments (expenses)
    cur.execute("""
        SELECT payment_id, payment_date, amount, payment_method, notes
        FROM payments
        WHERE payment_date >= %s AND payment_date < %s
          AND reserve_number IS NULL
          AND amount < 0
        ORDER BY payment_date, payment_id
    """, (s, e))
    
    expenses = cur.fetchall()
    print(f"=== Migrate 2012 Negative Payments to Receipts ===")
    print(f"Found {len(expenses)} expense payments to migrate")
    
    if not expenses:
        print("Nothing to migrate")
        cur.close()
        conn.close()
        return
    
    # Preview sample
    print(f"\nSample 10 to migrate:")
    print(f"{'Date':<12} {'Amount':>10} {'Vendor':<30} Category")
    print('-' * 80)
    
    for row in expenses[:10]:
        payment_id, pmt_date, amount, method, notes = row
        vendor = extract_vendor(notes)
        category = categorize(vendor, notes)
        print(f"{pmt_date} ${abs(amount):>9,.2f} {vendor:<30} {category}")
    
    if not args.write:
        print(f"\n[WARN]  DRY RUN - Use --write to migrate")
        cur.close()
        conn.close()
        return
    
    # Create backup
    backup_table = f"payments_backup_migrate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\n📦 Creating backup: {backup_table}")
    
    payment_ids = [r[0] for r in expenses]
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM payments WHERE payment_id = ANY(%s)
    """, (payment_ids,))
    print(f"   ✓ Backed up {cur.rowcount} payments")
    
    # Introspect receipts schema
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'receipts'
        ORDER BY ordinal_position
    """)
    cols = {r[0] for r in cur.fetchall()}
    
    # Build INSERT based on available columns
    insert_cols = ['receipt_date', 'gross_amount', 'gst_amount', 'net_amount', 'category']
    insert_vals = ['%s', '%s', '%s', '%s', '%s']
    
    if 'vendor_name' in cols:
        insert_cols.append('vendor_name')
        insert_vals.append('%s')
    elif 'vendor_extracted' in cols:
        insert_cols.append('vendor_extracted')
        insert_vals.append('%s')
    
    if 'description' in cols:
        insert_cols.append('description')
        insert_vals.append('%s')
    elif 'notes' in cols:
        insert_cols.append('notes')
        insert_vals.append('%s')
    
    if 'source_reference' in cols:
        insert_cols.append('source_reference')
        insert_vals.append('%s')
    
    # Add source_hash if exists to avoid duplicates
    if 'source_hash' in cols:
        insert_cols.append('source_hash')
        insert_vals.append('%s')
    
    insert_sql = f"""
        INSERT INTO receipts ({', '.join(insert_cols)})
        VALUES ({', '.join(insert_vals)})
    """
    
    # Migrate each expense
    print(f"\n🔄 Migrating {len(expenses)} expenses to receipts...")
    migrated = 0
    
    for row in expenses:
        payment_id, pmt_date, amount, method, notes = row
        vendor = extract_vendor(notes)
        category = categorize(vendor, notes)
        
        gross = abs(amount)  # Make positive
        gst, net = calculate_gst(gross)
        
        # Build values tuple based on available columns
        values = [pmt_date, gross, gst, net, category]
        
        if 'vendor_name' in cols or 'vendor_extracted' in cols:
            values.append(vendor)
        
        if 'description' in cols or 'notes' in cols:
            desc = f"Migrated from payment {payment_id}: {notes or ''}"
            values.append(desc[:500])  # Truncate if needed
        
        if 'source_reference' in cols:
            values.append(f"PAYMENT_{payment_id}")
        
        if 'source_hash' in cols:
            import hashlib
            hash_str = f"{pmt_date}_{vendor}_{gross}_{payment_id}"
            source_hash = hashlib.sha256(hash_str.encode()).hexdigest()
            values.append(source_hash)
        
        cur.execute(insert_sql, values)
        migrated += 1
        
        if migrated % 100 == 0:
            print(f"   ... {migrated} migrated")
    
    # Delete migrated payments
    print(f"\n🗑️  Deleting {len(expenses)} migrated payments...")
    cur.execute("DELETE FROM payments WHERE payment_id = ANY(%s)", (payment_ids,))
    deleted = cur.rowcount
    
    conn.commit()
    
    print(f"\n{'='*80}")
    print("[OK] MIGRATION COMPLETE")
    print("=" * 80)
    print(f"Migrated: {migrated} receipts")
    print(f"Deleted: {deleted} payments")
    print(f"Backup: {backup_table}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
