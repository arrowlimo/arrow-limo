#!/usr/bin/env python3
"""
Create missing Fibrenew receipt records in database.
Assumes all invoices were paid by cash unless documented otherwise (cheque/etransfer in banking).
"""

import pandas as pd
from decimal import Decimal
from datetime import datetime
from collections import defaultdict
import psycopg2
import os
import hashlib
import argparse

EXCEL_FILE = r'L:\limo\pdf\2012\fibrenew.xlsx'

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def parse_date(val):
    if pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        for fmt in ['%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d']:
            try:
                return datetime.strptime(val.strip(), fmt).date()
            except:
                continue
    return None

def parse_amount(val):
    if pd.isna(val):
        return None
    try:
        return Decimal(str(val))
    except:
        return None

def calculate_gst(gross_amount, tax_rate=Decimal('0.05')):
    """GST is INCLUDED in amount (Alberta 5% GST)."""
    gst_amount = gross_amount * tax_rate / (Decimal('1') + tax_rate)
    net_amount = gross_amount - gst_amount
    return gst_amount, net_amount

def generate_hash(date, description, amount):
    """Generate deterministic hash for deduplication."""
    hash_input = f"{date}|{description}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Apply changes to database')
    args = parser.parse_args()
    
    # Read Excel data
    df = pd.read_excel(EXCEL_FILE, header=None)
    
    print("="*80)
    print("FIBRENEW RECEIPT CREATION")
    print("="*80)
    
    # Parse all invoices
    all_invoices = []
    seen_invoices = {}
    
    for idx, row in df.iterrows():
        col0 = str(row[0]).strip()
        if col0 and col0 not in ['inv', 'pmt', 'statement', 'nan'] and not 'balance' in str(row[1]).lower():
            inv_date = parse_date(row[1])
            inv_amt = parse_amount(row[2])
            notes = str(row[3]) if not pd.isna(row[3]) else ''
            
            if inv_date and col0 not in seen_invoices:
                amount = inv_amt if inv_amt else Decimal('0')
                
                if amount >= Decimal('1000'):
                    category = 'rent'
                elif Decimal('100') <= amount < Decimal('1000'):
                    category = 'utilities'
                elif amount < Decimal('0'):
                    category = 'credit'
                else:
                    category = 'other'
                
                all_invoices.append({
                    'invoice': col0,
                    'date': inv_date,
                    'category': category,
                    'amount': amount,
                    'notes': notes
                })
                seen_invoices[col0] = True
    
    # Add 2019-2025 statement invoices
    statement_invoices = [
        # 2019
        {'invoice': '8696', 'date': datetime(2019, 2, 1).date(), 'category': 'utilities', 'amount': Decimal('301.48')},
        {'invoice': '8693', 'date': datetime(2019, 3, 1).date(), 'category': 'rent', 'amount': Decimal('682.50')},
        {'invoice': '8697', 'date': datetime(2019, 3, 1).date(), 'category': 'utilities', 'amount': Decimal('345.88')},
        {'invoice': '8695', 'date': datetime(2019, 4, 1).date(), 'category': 'rent', 'amount': Decimal('682.50')},
        {'invoice': '8690', 'date': datetime(2019, 5, 7).date(), 'category': 'utilities', 'amount': Decimal('295.69')},
        {'invoice': '8691', 'date': datetime(2019, 5, 7).date(), 'category': 'rent', 'amount': Decimal('682.50')},
        {'invoice': '8743', 'date': datetime(2019, 5, 31).date(), 'category': 'rent', 'amount': Decimal('682.50')},
        {'invoice': '8744', 'date': datetime(2019, 5, 31).date(), 'category': 'utilities', 'amount': Decimal('254.32')},
        {'invoice': '8832', 'date': datetime(2019, 7, 1).date(), 'category': 'rent', 'amount': Decimal('682.50')},
        {'invoice': '8833', 'date': datetime(2019, 7, 11).date(), 'category': 'utilities', 'amount': Decimal('153.13')},
        {'invoice': '8894', 'date': datetime(2019, 8, 6).date(), 'category': 'utilities', 'amount': Decimal('144.89')},
        {'invoice': '8895', 'date': datetime(2019, 8, 6).date(), 'category': 'rent', 'amount': Decimal('682.50')},
        {'invoice': '8942', 'date': datetime(2019, 9, 4).date(), 'category': 'rent', 'amount': Decimal('682.50')},
        {'invoice': '8943', 'date': datetime(2019, 9, 4).date(), 'category': 'utilities', 'amount': Decimal('183.91')},
        {'invoice': '8979', 'date': datetime(2019, 10, 1).date(), 'category': 'rent', 'amount': Decimal('682.50')},
        {'invoice': '8980', 'date': datetime(2019, 10, 1).date(), 'category': 'utilities', 'amount': Decimal('152.62')},
        {'invoice': '9025', 'date': datetime(2019, 11, 1).date(), 'category': 'utilities', 'amount': Decimal('163.46')},
        {'invoice': '9066', 'date': datetime(2019, 11, 6).date(), 'category': 'rent', 'amount': Decimal('682.50')},
        {'invoice': '9067', 'date': datetime(2019, 11, 6).date(), 'category': 'utilities', 'amount': Decimal('157.88')},
        {'invoice': '9103', 'date': datetime(2019, 12, 4).date(), 'category': 'utilities', 'amount': Decimal('126.60')},
        # 2020
        {'invoice': '9135', 'date': datetime(2020, 1, 1).date(), 'category': 'rent', 'amount': Decimal('682.50')},
        {'invoice': '9139', 'date': datetime(2020, 1, 8).date(), 'category': 'utilities', 'amount': Decimal('190.20')},
        {'invoice': '9172', 'date': datetime(2020, 2, 1).date(), 'category': 'rent', 'amount': Decimal('682.50')},
        {'invoice': '9201', 'date': datetime(2020, 2, 14).date(), 'category': 'utilities', 'amount': Decimal('228.12')},
        {'invoice': '9239', 'date': datetime(2020, 3, 2).date(), 'category': 'rent', 'amount': Decimal('682.50')},
        {'invoice': '9288', 'date': datetime(2020, 3, 30).date(), 'category': 'utilities', 'amount': Decimal('304.47')},
        {'invoice': '9287', 'date': datetime(2020, 4, 1).date(), 'category': 'rent', 'amount': Decimal('682.50')},
        {'invoice': '9325', 'date': datetime(2020, 5, 14).date(), 'category': 'utilities', 'amount': Decimal('199.26')},
        {'invoice': '9392', 'date': datetime(2020, 6, 23).date(), 'category': 'utilities', 'amount': Decimal('156.64')},
        {'invoice': '9407', 'date': datetime(2020, 7, 2).date(), 'category': 'rent', 'amount': Decimal('840.00')},
        {'invoice': '9436', 'date': datetime(2020, 7, 22).date(), 'category': 'utilities', 'amount': Decimal('134.81')},
        {'invoice': '9490', 'date': datetime(2020, 8, 5).date(), 'category': 'rent', 'amount': Decimal('840.00')},
        {'invoice': '9542', 'date': datetime(2020, 9, 1).date(), 'category': 'rent', 'amount': Decimal('840.00')},
        {'invoice': '9561', 'date': datetime(2020, 9, 10).date(), 'category': 'utilities', 'amount': Decimal('142.63')},
        {'invoice': '9609', 'date': datetime(2020, 10, 1).date(), 'category': 'rent', 'amount': Decimal('840.00')},
        {'invoice': '9623', 'date': datetime(2020, 10, 8).date(), 'category': 'utilities', 'amount': Decimal('145.20')},
        {'invoice': '9670', 'date': datetime(2020, 11, 1).date(), 'category': 'rent', 'amount': Decimal('840.00')},
        {'invoice': '9694', 'date': datetime(2020, 11, 18).date(), 'category': 'utilities', 'amount': Decimal('162.21')},
        {'invoice': '9727', 'date': datetime(2020, 12, 1).date(), 'category': 'rent', 'amount': Decimal('840.00')},
        {'invoice': '9742', 'date': datetime(2020, 12, 7).date(), 'category': 'utilities', 'amount': Decimal('191.25')},
        # 2021
        {'invoice': '9767', 'date': datetime(2021, 1, 1).date(), 'category': 'rent', 'amount': Decimal('840.00')},
        {'invoice': '9772', 'date': datetime(2021, 1, 18).date(), 'category': 'utilities', 'amount': Decimal('201.35')},
        {'invoice': '9800', 'date': datetime(2021, 2, 1).date(), 'category': 'rent', 'amount': Decimal('840.00')},
        {'invoice': '9815', 'date': datetime(2021, 2, 5).date(), 'category': 'utilities', 'amount': Decimal('169.44')},
        {'invoice': '9866', 'date': datetime(2021, 3, 1).date(), 'category': 'rent', 'amount': Decimal('840.00')},
        {'invoice': '9885', 'date': datetime(2021, 3, 8).date(), 'category': 'utilities', 'amount': Decimal('220.34')},
        {'invoice': '9956', 'date': datetime(2021, 4, 6).date(), 'category': 'rent', 'amount': Decimal('840.00')},
        # 2024-2025
        {'invoice': '12131', 'date': datetime(2024, 1, 2).date(), 'category': 'rent', 'amount': Decimal('1102.50')},
        {'invoice': '12132', 'date': datetime(2024, 2, 1).date(), 'category': 'rent', 'amount': Decimal('1102.50')},
        {'invoice': '12133', 'date': datetime(2024, 3, 1).date(), 'category': 'rent', 'amount': Decimal('1102.50')},
        {'invoice': '12177', 'date': datetime(2024, 4, 1).date(), 'category': 'rent', 'amount': Decimal('1102.50')},
        {'invoice': '12226', 'date': datetime(2024, 5, 1).date(), 'category': 'rent', 'amount': Decimal('1102.50')},
        {'invoice': '12419', 'date': datetime(2024, 8, 1).date(), 'category': 'rent', 'amount': Decimal('1102.50')},
        {'invoice': '12494', 'date': datetime(2024, 9, 1).date(), 'category': 'rent', 'amount': Decimal('1102.50')},
        {'invoice': '12540', 'date': datetime(2024, 10, 1).date(), 'category': 'rent', 'amount': Decimal('1102.50')},
        {'invoice': '12601', 'date': datetime(2024, 11, 1).date(), 'category': 'rent', 'amount': Decimal('1102.50')},
        {'invoice': '12664', 'date': datetime(2024, 12, 2).date(), 'category': 'rent', 'amount': Decimal('1102.50')},
        {'invoice': '12714', 'date': datetime(2025, 1, 1).date(), 'category': 'rent', 'amount': Decimal('1102.50')},
        {'invoice': '12775', 'date': datetime(2025, 2, 3).date(), 'category': 'rent', 'amount': Decimal('1102.50')},
        {'invoice': '12835', 'date': datetime(2025, 3, 3).date(), 'category': 'rent', 'amount': Decimal('1102.50')},
        {'invoice': '12909', 'date': datetime(2025, 4, 1).date(), 'category': 'rent', 'amount': Decimal('1102.50')},
        {'invoice': '12973', 'date': datetime(2025, 5, 1).date(), 'category': 'rent', 'amount': Decimal('1102.50')},
        {'invoice': '13041', 'date': datetime(2025, 6, 1).date(), 'category': 'rent', 'amount': Decimal('1102.50')},
        {'invoice': '13103', 'date': datetime(2025, 7, 1).date(), 'category': 'rent', 'amount': Decimal('1102.50')},
        {'invoice': '13180', 'date': datetime(2025, 8, 1).date(), 'category': 'rent', 'amount': Decimal('1260.00')},
        {'invoice': '13248', 'date': datetime(2025, 9, 1).date(), 'category': 'rent', 'amount': Decimal('1260.00')},
        {'invoice': '13310', 'date': datetime(2025, 10, 1).date(), 'category': 'rent', 'amount': Decimal('1260.00')},
        {'invoice': '13379', 'date': datetime(2025, 11, 1).date(), 'category': 'rent', 'amount': Decimal('1260.00')},
    ]
    
    for inv in statement_invoices:
        inv['notes'] = ''
    
    all_invoices.extend(statement_invoices)
    
    print(f"\nTotal invoices to process: {len(all_invoices)}")
    
    # Connect to database
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Pre-load existing receipt hashes
    cur.execute("SELECT source_hash FROM receipts WHERE source_hash IS NOT NULL")
    existing_hashes = {row[0] for row in cur.fetchall()}
    print(f"Existing receipts in database: {len(existing_hashes)}")
    
    # Prepare receipts to create
    receipts_to_create = []
    receipts_skipped = []
    
    for inv in all_invoices:
        if inv['amount'] <= 0:
            continue  # Skip credits
        
        # Generate description and hash
        desc_type = 'Office Rent' if inv['category'] == 'rent' else 'Office Utilities'
        description = f"Fibrenew {desc_type} - Invoice #{inv['invoice']}"
        source_hash = generate_hash(inv['date'], description, inv['amount'])
        
        if source_hash in existing_hashes:
            receipts_skipped.append(inv)
            continue
        
        # Calculate GST (included)
        gst, net = calculate_gst(inv['amount'])
        
        receipts_to_create.append({
            'date': inv['date'],
            'vendor': 'Fibrenew',
            'gross_amount': float(inv['amount']),
            'gst_amount': float(gst),
            'net_amount': float(net),
            'description': description,
            'category': inv['category'],
            'source_hash': source_hash,
            'invoice_ref': inv['invoice']
        })
        existing_hashes.add(source_hash)  # Add to set for next iteration
    
    print(f"\nReceipts to create: {len(receipts_to_create)}")
    print(f"Receipts already exist (skipped): {len(receipts_skipped)}")
    
    if len(receipts_to_create) == 0:
        print("\n✓ All Fibrenew invoices already have receipts in database!")
        cur.close()
        conn.close()
        return
    
    # Show ALL receipts to create with invoice numbers
    print(f"\nReceipts to create (all {len(receipts_to_create)}):")
    for receipt in receipts_to_create:
        print(f"  {receipt['date']} | Invoice #{receipt['invoice_ref']:5} | ${receipt['gross_amount']:>8,.2f} | {receipt['category']:10} | {receipt['description']}")
    
    if not args.write:
        print(f"\n{'='*80}")
        print("DRY RUN - No changes made")
        print("Run with --write to create receipts")
        print(f"{'='*80}")
        cur.close()
        conn.close()
        return
    
    # Create receipts
    print(f"\nCreating {len(receipts_to_create)} receipts...")
    
    for receipt in receipts_to_create:
        cur.execute("""
            INSERT INTO receipts (
                receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
                description, category, source_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            receipt['date'],
            receipt['vendor'],
            receipt['gross_amount'],
            receipt['gst_amount'],
            receipt['net_amount'],
            receipt['description'],
            receipt['category'],
            receipt['source_hash']
        ))
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\n{'='*80}")
    print("✓ RECEIPTS CREATED SUCCESSFULLY")
    print(f"{'='*80}")
    print(f"\nCreated {len(receipts_to_create)} Fibrenew receipt records")
    print(f"Total amount: ${sum(r['gross_amount'] for r in receipts_to_create):,.2f}")
    
    # Breakdown by year
    by_year = defaultdict(lambda: {'count': 0, 'amount': Decimal('0')})
    for receipt in receipts_to_create:
        year = receipt['date'].year
        by_year[year]['count'] += 1
        by_year[year]['amount'] += Decimal(str(receipt['gross_amount']))
    
    print(f"\nReceipts created by year:")
    for year in sorted(by_year.keys()):
        print(f"  {year}: {by_year[year]['count']} receipts (${by_year[year]['amount']:,.2f})")

if __name__ == '__main__':
    main()
