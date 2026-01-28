import os
import psycopg2
import csv
import hashlib
from decimal import Decimal

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
)

cur = conn.cursor()

# Parse first record from CSV
wix_file = 'l:\\limo\\wix\\billing_history_Dec_06_2025 (1).csv'

records_to_check = []

with open(wix_file, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader, start=2):
        if i > 10:  # Check first 10 records
            break
        
        date_str = row.get('Date', '').strip()
        amount_str = row.get('Amount', '').strip()
        subscription = row.get('Subscription', '').strip()
        site = row.get('Site Name', '').strip()
        
        # Parse date
        from datetime import datetime
        try:
            dt = datetime.strptime(date_str, "%b %d %Y")
            parsed_date = dt.strftime("%Y-%m-%d")
        except:
            continue
        
        # Parse amount
        try:
            cleaned = amount_str.strip().replace('CA$', '').replace('$', '').strip()
            amount = float(cleaned)
        except:
            continue
        
        # Skip refunds
        if amount < 0:
            continue
        
        # Generate vendor and hash
        vendor = f"Wix - {subscription} ({site})" if site else f"Wix - {subscription}"
        hash_input = f"{parsed_date}|{vendor}|{amount:.2f}".encode('utf-8')
        source_hash = hashlib.sha256(hash_input).hexdigest()
        
        records_to_check.append({
            'date': parsed_date,
            'vendor': vendor,
            'amount': amount,
            'hash': source_hash,
            'row': i
        })
        
        print(f"Row {i}: {parsed_date} {vendor:50} ${amount:8.2f}")
        print(f"        Hash: {source_hash}")

# Check which ones exist in database
print("\n" + "="*80)
print("Checking database for duplicates...\n")

for rec in records_to_check:
    cur.execute("SELECT receipt_id, vendor_name, gross_amount FROM receipts WHERE source_hash = %s", 
                (rec['hash'],))
    result = cur.fetchone()
    
    if result:
        receipt_id, existing_vendor, existing_amount = result
        print(f"❌ FOUND in DB (receipt_id={receipt_id}):")
        print(f"   Expected:  {rec['vendor']} ${rec['amount']:.2f}")
        print(f"   Existing:  {existing_vendor} ${existing_amount:.2f}")
    else:
        print(f"✅ NOT in DB: {rec['vendor']} ${rec['amount']:.2f}")

conn.close()
