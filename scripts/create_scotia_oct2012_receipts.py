#!/usr/bin/env python3
"""
Create receipts for all Scotia Bank October 2012 transactions that don't have receipts.
"""

import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def calculate_gst(gross_amount, tax_rate=0.05):
    """GST is INCLUDED in amount (Alberta 5% GST)."""
    gross_amount = float(gross_amount)
    gst_amount = gross_amount * tax_rate / (1 + tax_rate)
    net_amount = gross_amount - gst_amount
    return round(gst_amount, 2), round(net_amount, 2)

def extract_vendor_name(description):
    """Extract vendor name from transaction description."""
    desc = description.strip()
    
    # Clean up common patterns
    if desc.startswith('CHQ '):
        return 'UNKNOWN PAYEE (CHEQUE)'
    
    # Remove common prefixes
    for prefix in ['POINT OF SALE PURCHASE', 'RED DEER', 'ABCA', 'DEERPARK', 'HIGHLAND']:
        desc = desc.replace(prefix, '').strip()
    
    # Remove location codes like #04240, (C-STOR, etc.
    import re
    desc = re.sub(r'#\d+', '', desc)
    desc = re.sub(r'\(C-STOR.*?\)', '', desc)
    desc = re.sub(r'\(.*?RED DEER.*?\)', '', desc)
    desc = re.sub(r'RED DEER', '', desc)
    
    # Clean up extra spaces
    desc = ' '.join(desc.split())
    
    return desc if desc else 'UNKNOWN VENDOR'

def determine_category(description):
    """Determine receipt category from description."""
    desc_upper = description.upper()
    
    if any(x in desc_upper for x in ['LIQUOR', 'BEER', 'WINE']):
        return 'Liquor/Entertainment'
    elif any(x in desc_upper for x in ['PETRO', 'SHELL', 'MOHAWK', 'GAS', 'FUEL']):
        return 'Fuel'
    elif any(x in desc_upper for x in ['GNC', 'SHOPPERS', 'DRUG MART']):
        return 'Supplies'
    elif 'CENTEX' in desc_upper:
        return 'Fuel'  # Centex is a gas station
    elif any(x in desc_upper for x in ['TRUCK', 'RENTAL', 'ACE']):
        return 'Vehicle Rental'
    elif 'OD FEE' in desc_upper or 'OVERDRAWN' in desc_upper or 'SERVICE CHARGE' in desc_upper:
        return 'Bank Fees'
    elif 'CHQ' in desc_upper or 'CHEQUE' in desc_upper:
        return 'Unknown'
    elif 'DEPOSIT' in desc_upper:
        return 'Income - Card Payments'
    elif 'COPIES' in desc_upper:
        return 'Office Supplies'
    else:
        return 'Unknown'

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 80)
print("CREATE RECEIPTS FOR SCOTIA BANK OCTOBER 2012")
print("=" * 80)

# Get all Scotia Bank Oct 2012 transactions without receipts
cur.execute("""
    SELECT bt.transaction_id, bt.transaction_date, bt.debit_amount, bt.credit_amount, 
           bt.description
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.bank_id = 2
      AND bt.transaction_date >= '2012-10-01' AND bt.transaction_date <= '2012-10-31'
      AND r.receipt_id IS NULL
    ORDER BY bt.transaction_date, bt.transaction_id
""")

transactions = cur.fetchall()
print(f"\nFound {len(transactions)} transactions without receipts\n")

# Get next receipt_id
cur.execute("SELECT COALESCE(MAX(receipt_id), 0) + 1 FROM receipts")
next_receipt_id = cur.fetchone()[0]

created_count = 0
skipped_count = 0

for tx_id, tx_date, debit, credit, description in transactions:
    # Determine if expense (debit) or income (credit)
    if debit and debit > 0:
        gross_amount = debit
        is_expense = True
    elif credit and credit > 0:
        gross_amount = credit
        is_expense = False
    else:
        print(f"  ⚠️  TX {tx_id}: Skipping - zero amount")
        skipped_count += 1
        continue
    
    # Extract vendor and category
    vendor_name = extract_vendor_name(description)
    category = determine_category(description)
    
    # Calculate GST (only for expenses, not income)
    if is_expense and gross_amount > 0:
        gst_amount, net_amount = calculate_gst(gross_amount)
    else:
        gst_amount = 0.00
        net_amount = gross_amount
    
    # Create receipt
    cur.execute("""
        INSERT INTO receipts (
            receipt_id, receipt_date, vendor_name, gross_amount, 
            gst_amount, net_amount, category, 
            banking_transaction_id, mapped_bank_account_id,
            created_from_banking
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """, (
        next_receipt_id,
        tx_date,
        vendor_name,
        gross_amount,
        gst_amount,
        net_amount,
        category,
        tx_id,
        2,  # Scotia Bank
        True
    ))
    
    created_count += 1
    
    tx_type = 'EXPENSE' if is_expense else 'INCOME'
    print(f"✅ Receipt {next_receipt_id:6d} | TX {tx_id:6d} | {tx_date} | {tx_type:7} | ${gross_amount:>10,.2f} | {vendor_name[:30]}")
    
    next_receipt_id += 1

# Commit changes
conn.commit()

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"✅ Created receipts: {created_count}")
print(f"⚠️  Skipped (zero amount): {skipped_count}")
print(f"✅ ALL CHANGES COMMITTED")

# Verify
cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions bt
    JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.bank_id = 2
      AND bt.transaction_date >= '2012-10-01' AND bt.transaction_date <= '2012-10-31'
""")

final_count = cur.fetchone()[0]
print(f"\nVerification: {final_count} Scotia Oct 2012 transactions now have receipts")

cur.close()
conn.close()
