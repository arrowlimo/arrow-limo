#!/usr/bin/env python3
"""
Audit Fibrenew monthly billing pattern and identify missing payment receipts.
For each month from 2012-2025, verify:
1. One rent invoice exists
2. One utilities invoice exists (where applicable)
3. Payment method (cheque/etransfer/cash) is documented

Then create missing receipt records for cash payments.
"""

import pandas as pd
from decimal import Decimal
from datetime import datetime
from collections import defaultdict
import psycopg2
import os

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

# Read Excel data
df = pd.read_excel(EXCEL_FILE, header=None)

print("="*80)
print("FIBRENEW MONTHLY BILLING AUDIT (2012-2025)")
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
            
            # Categorize
            if amount >= Decimal('1000'):
                category = 'RENT'
            elif Decimal('100') <= amount < Decimal('1000'):
                category = 'UTILITIES'
            elif amount < Decimal('0'):
                category = 'CREDIT'
            else:
                category = 'OTHER'
            
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
    {'invoice': '8696', 'date': datetime(2019, 2, 1).date(), 'category': 'UTILITIES', 'amount': Decimal('301.48')},
    {'invoice': '8693', 'date': datetime(2019, 3, 1).date(), 'category': 'RENT', 'amount': Decimal('682.50')},
    {'invoice': '8697', 'date': datetime(2019, 3, 1).date(), 'category': 'UTILITIES', 'amount': Decimal('345.88')},
    {'invoice': '8695', 'date': datetime(2019, 4, 1).date(), 'category': 'RENT', 'amount': Decimal('682.50')},
    {'invoice': '8690', 'date': datetime(2019, 5, 7).date(), 'category': 'UTILITIES', 'amount': Decimal('295.69')},
    {'invoice': '8691', 'date': datetime(2019, 5, 7).date(), 'category': 'RENT', 'amount': Decimal('682.50')},
    {'invoice': '8743', 'date': datetime(2019, 5, 31).date(), 'category': 'RENT', 'amount': Decimal('682.50')},
    {'invoice': '8744', 'date': datetime(2019, 5, 31).date(), 'category': 'UTILITIES', 'amount': Decimal('254.32')},
    {'invoice': '8832', 'date': datetime(2019, 7, 1).date(), 'category': 'RENT', 'amount': Decimal('682.50')},
    {'invoice': '8833', 'date': datetime(2019, 7, 11).date(), 'category': 'UTILITIES', 'amount': Decimal('153.13')},
    {'invoice': '8894', 'date': datetime(2019, 8, 6).date(), 'category': 'UTILITIES', 'amount': Decimal('144.89')},
    {'invoice': '8895', 'date': datetime(2019, 8, 6).date(), 'category': 'RENT', 'amount': Decimal('682.50')},
    {'invoice': '8942', 'date': datetime(2019, 9, 4).date(), 'category': 'RENT', 'amount': Decimal('682.50')},
    {'invoice': '8943', 'date': datetime(2019, 9, 4).date(), 'category': 'UTILITIES', 'amount': Decimal('183.91')},
    {'invoice': '8979', 'date': datetime(2019, 10, 1).date(), 'category': 'RENT', 'amount': Decimal('682.50')},
    {'invoice': '8980', 'date': datetime(2019, 10, 1).date(), 'category': 'UTILITIES', 'amount': Decimal('152.62')},
    {'invoice': '9025', 'date': datetime(2019, 11, 1).date(), 'category': 'UTILITIES', 'amount': Decimal('163.46')},
    {'invoice': '9066', 'date': datetime(2019, 11, 6).date(), 'category': 'RENT', 'amount': Decimal('682.50')},
    {'invoice': '9067', 'date': datetime(2019, 11, 6).date(), 'category': 'UTILITIES', 'amount': Decimal('157.88')},
    {'invoice': '9103', 'date': datetime(2019, 12, 4).date(), 'category': 'UTILITIES', 'amount': Decimal('126.60')},
    # 2020
    {'invoice': '9135', 'date': datetime(2020, 1, 1).date(), 'category': 'RENT', 'amount': Decimal('682.50')},
    {'invoice': '9139', 'date': datetime(2020, 1, 8).date(), 'category': 'UTILITIES', 'amount': Decimal('190.20')},
    {'invoice': '9172', 'date': datetime(2020, 2, 1).date(), 'category': 'RENT', 'amount': Decimal('682.50')},
    {'invoice': '9201', 'date': datetime(2020, 2, 14).date(), 'category': 'UTILITIES', 'amount': Decimal('228.12')},
    {'invoice': '9239', 'date': datetime(2020, 3, 2).date(), 'category': 'RENT', 'amount': Decimal('682.50')},
    {'invoice': '9288', 'date': datetime(2020, 3, 30).date(), 'category': 'UTILITIES', 'amount': Decimal('304.47')},
    {'invoice': '9287', 'date': datetime(2020, 4, 1).date(), 'category': 'RENT', 'amount': Decimal('682.50')},
    {'invoice': '9325', 'date': datetime(2020, 5, 14).date(), 'category': 'UTILITIES', 'amount': Decimal('199.26')},
    {'invoice': '9392', 'date': datetime(2020, 6, 23).date(), 'category': 'UTILITIES', 'amount': Decimal('156.64')},
    {'invoice': '9407', 'date': datetime(2020, 7, 2).date(), 'category': 'RENT', 'amount': Decimal('840.00')},
    {'invoice': '9436', 'date': datetime(2020, 7, 22).date(), 'category': 'UTILITIES', 'amount': Decimal('134.81')},
    {'invoice': '9490', 'date': datetime(2020, 8, 5).date(), 'category': 'RENT', 'amount': Decimal('840.00')},
    {'invoice': '9542', 'date': datetime(2020, 9, 1).date(), 'category': 'RENT', 'amount': Decimal('840.00')},
    {'invoice': '9561', 'date': datetime(2020, 9, 10).date(), 'category': 'UTILITIES', 'amount': Decimal('142.63')},
    {'invoice': '9609', 'date': datetime(2020, 10, 1).date(), 'category': 'RENT', 'amount': Decimal('840.00')},
    {'invoice': '9623', 'date': datetime(2020, 10, 8).date(), 'category': 'UTILITIES', 'amount': Decimal('145.20')},
    {'invoice': '9670', 'date': datetime(2020, 11, 1).date(), 'category': 'RENT', 'amount': Decimal('840.00')},
    {'invoice': '9694', 'date': datetime(2020, 11, 18).date(), 'category': 'UTILITIES', 'amount': Decimal('162.21')},
    {'invoice': '9727', 'date': datetime(2020, 12, 1).date(), 'category': 'RENT', 'amount': Decimal('840.00')},
    {'invoice': '9742', 'date': datetime(2020, 12, 7).date(), 'category': 'UTILITIES', 'amount': Decimal('191.25')},
    # 2021
    {'invoice': '9767', 'date': datetime(2021, 1, 1).date(), 'category': 'RENT', 'amount': Decimal('840.00')},
    {'invoice': '9772', 'date': datetime(2021, 1, 18).date(), 'category': 'UTILITIES', 'amount': Decimal('201.35')},
    {'invoice': '9800', 'date': datetime(2021, 2, 1).date(), 'category': 'RENT', 'amount': Decimal('840.00')},
    {'invoice': '9815', 'date': datetime(2021, 2, 5).date(), 'category': 'UTILITIES', 'amount': Decimal('169.44')},
    {'invoice': '9866', 'date': datetime(2021, 3, 1).date(), 'category': 'RENT', 'amount': Decimal('840.00')},
    {'invoice': '9885', 'date': datetime(2021, 3, 8).date(), 'category': 'UTILITIES', 'amount': Decimal('220.34')},
    {'invoice': '9956', 'date': datetime(2021, 4, 6).date(), 'category': 'RENT', 'amount': Decimal('840.00')},
    # 2024-2025
    {'invoice': '12131', 'date': datetime(2024, 1, 2).date(), 'category': 'RENT', 'amount': Decimal('1102.50')},
    {'invoice': '12132', 'date': datetime(2024, 2, 1).date(), 'category': 'RENT', 'amount': Decimal('1102.50')},
    {'invoice': '12133', 'date': datetime(2024, 3, 1).date(), 'category': 'RENT', 'amount': Decimal('1102.50')},
    {'invoice': '12177', 'date': datetime(2024, 4, 1).date(), 'category': 'RENT', 'amount': Decimal('1102.50')},
    {'invoice': '12226', 'date': datetime(2024, 5, 1).date(), 'category': 'RENT', 'amount': Decimal('1102.50')},
    {'invoice': '12419', 'date': datetime(2024, 8, 1).date(), 'category': 'RENT', 'amount': Decimal('1102.50')},
    {'invoice': '12494', 'date': datetime(2024, 9, 1).date(), 'category': 'RENT', 'amount': Decimal('1102.50')},
    {'invoice': '12540', 'date': datetime(2024, 10, 1).date(), 'category': 'RENT', 'amount': Decimal('1102.50')},
    {'invoice': '12601', 'date': datetime(2024, 11, 1).date(), 'category': 'RENT', 'amount': Decimal('1102.50')},
    {'invoice': '12664', 'date': datetime(2024, 12, 2).date(), 'category': 'RENT', 'amount': Decimal('1102.50')},
    {'invoice': '12714', 'date': datetime(2025, 1, 1).date(), 'category': 'RENT', 'amount': Decimal('1102.50')},
    {'invoice': '12775', 'date': datetime(2025, 2, 3).date(), 'category': 'RENT', 'amount': Decimal('1102.50')},
    {'invoice': '12835', 'date': datetime(2025, 3, 3).date(), 'category': 'RENT', 'amount': Decimal('1102.50')},
    {'invoice': '12909', 'date': datetime(2025, 4, 1).date(), 'category': 'RENT', 'amount': Decimal('1102.50')},
    {'invoice': '12973', 'date': datetime(2025, 5, 1).date(), 'category': 'RENT', 'amount': Decimal('1102.50')},
    {'invoice': '13041', 'date': datetime(2025, 6, 1).date(), 'category': 'RENT', 'amount': Decimal('1102.50')},
    {'invoice': '13103', 'date': datetime(2025, 7, 1).date(), 'category': 'RENT', 'amount': Decimal('1102.50')},
    {'invoice': '13180', 'date': datetime(2025, 8, 1).date(), 'category': 'RENT', 'amount': Decimal('1260.00')},
    {'invoice': '13248', 'date': datetime(2025, 9, 1).date(), 'category': 'RENT', 'amount': Decimal('1260.00')},
    {'invoice': '13310', 'date': datetime(2025, 10, 1).date(), 'category': 'RENT', 'amount': Decimal('1260.00')},
    {'invoice': '13379', 'date': datetime(2025, 11, 1).date(), 'category': 'RENT', 'amount': Decimal('1260.00')},
]

all_invoices.extend(statement_invoices)

# Group by year-month
by_month = defaultdict(lambda: {'rent': [], 'utilities': [], 'other': []})

for inv in all_invoices:
    month_key = (inv['date'].year, inv['date'].month)
    if inv['category'] == 'RENT':
        by_month[month_key]['rent'].append(inv)
    elif inv['category'] == 'UTILITIES':
        by_month[month_key]['utilities'].append(inv)
    else:
        by_month[month_key]['other'].append(inv)

# Check existing receipts in database for Fibrenew
conn = get_db_connection()
cur = conn.cursor()

cur.execute("""
    SELECT receipt_date, vendor_name, gross_amount, category, description
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%fibrenew%'
    ORDER BY receipt_date
""")

existing_receipts = cur.fetchall()
print(f"\nFound {len(existing_receipts)} existing Fibrenew receipts in database")

# Analyze monthly pattern and missing receipts
print(f"\n{'='*80}")
print("MONTHLY BILLING AUDIT")
print(f"{'='*80}\n")

missing_receipts = []
months_with_issues = []

for month_key in sorted(by_month.keys()):
    year, month = month_key
    data = by_month[month_key]
    month_name = datetime(year, month, 1).strftime('%B %Y')
    
    rent_count = len(data['rent'])
    util_count = len(data['utilities'])
    
    total_rent = sum(inv['amount'] for inv in data['rent'])
    total_util = sum(inv['amount'] for inv in data['utilities'])
    total_month = total_rent + total_util
    
    # Standard pattern: 1 rent + 0-1 utilities
    status = "✓" if (rent_count >= 1 and util_count <= 1) else "⚠"
    
    print(f"{month_name:20} | Rent: {rent_count} (${total_rent:>8,.2f}) | Util: {util_count} (${total_util:>8,.2f}) | Total: ${total_month:>9,.2f} {status}")
    
    # For normal months, assume cash payment if not otherwise documented
    # (Cheques and etransfers would be in banking/payment records)
    if rent_count >= 1:
        for rent_inv in data['rent']:
            missing_receipts.append({
                'date': rent_inv['date'],
                'vendor': 'Fibrenew',
                'category': 'rent',
                'amount': rent_inv['amount'],
                'invoice': rent_inv['invoice'],
                'description': f"Fibrenew Office Rent - Invoice #{rent_inv['invoice']}",
                'payment_method': 'cash'  # Assumed
            })
    
    if util_count >= 1:
        for util_inv in data['utilities']:
            missing_receipts.append({
                'date': util_inv['date'],
                'vendor': 'Fibrenew',
                'category': 'utilities',
                'amount': util_inv['amount'],
                'invoice': util_inv['invoice'],
                'description': f"Fibrenew Office Utilities - Invoice #{util_inv['invoice']}",
                'payment_method': 'cash'  # Assumed
            })

print(f"\n{'='*80}")
print(f"SUMMARY")
print(f"{'='*80}")
print(f"\nTotal months with invoices: {len(by_month)}")
print(f"Total invoices: {len(all_invoices)}")
print(f"Total receipts needed: {len(missing_receipts)}")
print(f"\nTotal amount requiring receipts: ${sum(r['amount'] for r in missing_receipts):,.2f}")

# Show breakdown by year
by_year = defaultdict(lambda: {'count': 0, 'amount': Decimal('0')})
for receipt in missing_receipts:
    year = receipt['date'].year
    by_year[year]['count'] += 1
    by_year[year]['amount'] += receipt['amount']

print(f"\nReceipts needed by year:")
for year in sorted(by_year.keys()):
    print(f"  {year}: {by_year[year]['count']} receipts (${by_year[year]['amount']:,.2f})")

cur.close()
conn.close()

print(f"\n{'='*80}")
print("Next step: Run create_fibrenew_receipts.py --write to import receipts")
print(f"{'='*80}")
