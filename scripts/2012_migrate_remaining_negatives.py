"""
Migrate remaining 34 negative 2012 payments (bank_transfer method).
These were missed because they had no notes or different patterns.
"""
import os
import psycopg2
import hashlib
from decimal import Decimal

DB = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'dbname': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '***REMOVED***'),
}

def calculate_gst(gross_amount):
    """Calculate GST included (5% Alberta)"""
    rate = 0.05
    gst = float(gross_amount) * rate / (1 + rate)
    net = float(gross_amount) - gst
    return round(gst, 2), round(net, 2)

def extract_vendor(notes):
    """Extract vendor from notes"""
    if not notes:
        return None
    
    # Check for QBO Import pattern
    if 'QBO Import:' in notes:
        parts = notes.split('QBO Import:')[1].split('|')
        if parts:
            vendor = parts[0].strip()
            # Clean up prefixes
            vendor = vendor.replace('PC-', '').replace('BR ', '').strip()
            return vendor
    
    return None

def categorize(vendor, notes):
    """Categorize based on keywords"""
    text = (vendor or '') + ' ' + (notes or '')
    text_lower = text.lower()
    
    if 'gnc' in text_lower or 'fuel' in text_lower or 'gas' in text_lower:
        return 'Fuel'
    
    # Bank transfers with no notes are likely expense transfers
    return 'General Expense'

conn = psycopg2.connect(**DB)
cur = conn.cursor()

# Introspect receipts schema
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'receipts'
    ORDER BY ordinal_position
""")
receipt_cols = {row[0] for row in cur.fetchall()}

# Get negative 2012 payments
cur.execute("""
    SELECT payment_id, payment_date, amount, payment_method, notes
    FROM payments 
    WHERE payment_date >= '2012-01-01' AND payment_date < '2013-01-01'
      AND amount < 0
    ORDER BY payment_id
""")

negatives = cur.fetchall()
print(f"=== Migrate Remaining 2012 Negative Payments ===")
print(f"Found {len(negatives)} negative payments to migrate\n")

if not negatives:
    print("No negative payments found")
    cur.close()
    conn.close()
    exit(0)

# Create backup
print("Creating backup...")
cur.execute(f"""
    CREATE TABLE IF NOT EXISTS payments_backup_migrate2_20251112 AS
    SELECT * FROM payments WHERE 1=0
""")
cur.execute(f"""
    INSERT INTO payments_backup_migrate2_20251112
    SELECT * FROM payments 
    WHERE payment_date >= '2012-01-01' AND payment_date < '2013-01-01'
      AND amount < 0
""")
conn.commit()
print(f"Backup created: payments_backup_migrate2_20251112 ({len(negatives)} payments)\n")

# Show sample
print("Sample 5 to migrate:")
for pid, pdate, amt, method, notes in negatives[:5]:
    vendor = extract_vendor(notes)
    category = categorize(vendor, notes)
    print(f"  {pdate} ${float(amt):>9,.2f} {category:<20} {vendor or '(no vendor)'}")

print("\n" + input("Press ENTER to proceed or Ctrl+C to cancel..."))

# Migrate to receipts
print("\nMigrating...")
count = 0

for payment_id, payment_date, amount, payment_method, notes in negatives:
    gross_amount = abs(float(amount))
    gst_amount, net_amount = calculate_gst(gross_amount)
    
    vendor = extract_vendor(notes)
    category = categorize(vendor, notes)
    
    # Generate unique hash
    hash_input = f"{payment_date}_{vendor or 'UNKNOWN'}_{gross_amount}_{payment_id}"
    source_hash = hashlib.sha256(hash_input.encode()).hexdigest()
    
    description = f"Migrated from payment {payment_id}"
    if notes:
        description += f": {notes}"
    
    # Build INSERT dynamically
    insert_cols = ['receipt_date', 'gross_amount', 'gst_amount', 'net_amount', 
                   'category', 'source_reference', 'source_hash']
    insert_vals = [payment_date, gross_amount, gst_amount, net_amount,
                   category, f"PAYMENT_{payment_id}", source_hash]
    
    if 'vendor_name' in receipt_cols:
        insert_cols.append('vendor_name')
        insert_vals.append(vendor)
    elif 'vendor_extracted' in receipt_cols:
        insert_cols.append('vendor_extracted')
        insert_vals.append(vendor)
    
    if 'description' in receipt_cols:
        insert_cols.append('description')
        insert_vals.append(description)
    elif 'notes' in receipt_cols:
        insert_cols.append('notes')
        insert_vals.append(description)
    
    cur.execute(f"""
        INSERT INTO receipts ({', '.join(insert_cols)})
        VALUES ({', '.join(['%s'] * len(insert_vals))})
    """, insert_vals)
    
    count += 1
    if count % 10 == 0:
        print(f"... {count} migrated")

print(f"\nMigrated {count} receipts")

# Delete from payments
cur.execute("""
    DELETE FROM payments 
    WHERE payment_date >= '2012-01-01' AND payment_date < '2013-01-01'
      AND amount < 0
""")
deleted = cur.rowcount
print(f"Deleted {deleted} payments")

conn.commit()

print("\n" + "=" * 80)
print("[OK] MIGRATION COMPLETE (PASS 2)")
print("=" * 80)

cur.close()
conn.close()
