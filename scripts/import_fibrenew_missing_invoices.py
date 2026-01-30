#!/usr/bin/env python3
"""
Import the 37 missing Fibrenew invoices from the statement.
Fibrenew records are authoritative - add these to match their billing.
"""

import psycopg2
import os
import csv
import hashlib
from decimal import Decimal
from datetime import datetime

print('='*100)
print('FIBRENEW MISSING INVOICES IMPORT')
print('='*100)

# Load missing invoices
csv_file = r'L:\limo\data\fibrenew_missing_invoices.csv'

invoices = []
with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        invoices.append({
            'date': datetime.strptime(row['date'], '%Y-%m-%d').date(),
            'invoice': row['invoice'],
            'amount': Decimal(row['amount']),
            'open_amount': Decimal(row['open_amount'])
        })

print(f'\nLoaded {len(invoices)} invoices to import')

# Connect to database
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print('\n\nIMPORTING RECEIPTS:')
print('-'*100)

created_count = 0
skipped_count = 0

for inv in invoices:
    # Calculate GST (5% included in amount)
    gross_amount = float(inv['amount'])
    gst_amount = gross_amount * 0.05 / 1.05
    net_amount = gross_amount - gst_amount
    
    # Determine category based on amount
    # $682.50 = monthly rent, smaller amounts = utilities
    if abs(gross_amount - 682.50) < 0.01 or abs(gross_amount - 840.00) < 0.01:
        category = 'rent'
        description = f"Invoice #{inv['invoice']} - Monthly office rent"
    else:
        category = 'rent'  # utilities still count as office rent expense
        description = f"Invoice #{inv['invoice']} - Office utilities"
    
    # Check if already exists (shouldn't, but double-check)
    cur.execute("""
        SELECT receipt_id FROM receipts
        WHERE receipt_date = %s
        AND ABS(gross_amount - %s) < 0.01
        AND (LOWER(vendor_name) LIKE '%%fibrenew%%' OR LOWER(description) LIKE '%%fibrenew%%')
    """, (inv['date'], gross_amount))
    
    if cur.fetchone():
        print(f'SKIP: {inv["date"]} #{inv["invoice"]} ${gross_amount:.2f} (already exists)')
        skipped_count += 1
        continue
    
    # Generate source hash
    hash_input = f"{inv['date']}|Fibrenew Central Alberta|{gross_amount:.2f}".encode('utf-8')
    source_hash = hashlib.sha256(hash_input).hexdigest()
    
    # Insert receipt
    cur.execute("""
        INSERT INTO receipts (
            receipt_date,
            vendor_name,
            gross_amount,
            gst_amount,
            net_amount,
            description,
            category,
            source_hash
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        RETURNING receipt_id
    """, (
        inv['date'],
        'Fibrenew Central Alberta',
        gross_amount,
        round(gst_amount, 2),
        round(net_amount, 2),
        description,
        category,
        source_hash
    ))
    
    receipt_id = cur.fetchone()[0]
    created_count += 1
    
    print(f'✓ Created receipt {receipt_id}: {inv["date"]} #{inv["invoice"]} ${gross_amount:.2f}')

# Commit
conn.commit()

print('\n\n' + '='*100)
print('IMPORT COMPLETE')
print('='*100)
print(f'Created: {created_count} receipts')
print(f'Skipped: {skipped_count} receipts (already existed)')

# Verify totals
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%fibrenew%'
       OR LOWER(description) LIKE '%fibrenew%'
""")

total_count, total_amount = cur.fetchone()
print(f'\n✓ Total Fibrenew receipts in database: {total_count}')
print(f'✓ Total amount: ${float(total_amount):,.2f}')

cur.close()
conn.close()

print('\n✓ Database updated to match Fibrenew statement')
