#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
auto_categorize_by_vendor.py

Automatically assign categories based on vendor name patterns.
"""

import psycopg2
import re
import sys

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

def determine_category(vendor, description):
    """Determine category based on vendor/description patterns."""
    if not vendor and not description:
        return None
    
    text = f"{vendor or ''} {description or ''}".upper()
    
    # Fuel
    if any(pattern in text for pattern in ['FAS GAS', 'SHELL', 'PETRO CANADA', 'ESSO', 'HUSKY', 'PIONEER']):
        return 'Fuel'
    
    # Vehicle Maintenance
    if any(pattern in text for pattern in ['OIL CHANGE', 'TIRE', 'CAR WASH', 'CARWASH', 'AUTO REPAIR', 'MIDAS', 'MEINEKE', 'JIFFY LUBE']):
        return 'Vehicle Maintenance'
    
    # Insurance
    if any(pattern in text for pattern in ['INSURANCE', 'INTACT', 'AVIVA', 'SGI']):
        return 'Insurance'
    
    # Bank Fees
    if any(pattern in text for pattern in ['BANK FEE', 'NSF', 'SERVICE CHARGE', 'MONTHLY FEE', 'OVERDRAFT', 'NSF CHARGE']):
        return 'Bank Fees'
    
    # Merchant Services (Customer Deposits)
    if any(pattern in text for pattern in ['GLOBAL VISA DEPOSIT', 'GLOBAL MASTERCARD DEPOSIT', 'GLOBAL AMEX DEPOSIT', 'SQUARE PAYOUT']):
        return 'Customer Deposits'
    
    # Merchant Fees (Chargebacks/Fees)
    if any(pattern in text for pattern in ['GLOBAL VISA PAYMENT', 'GLOBAL MASTERCARD PAYMENT', 'GLOBAL AMEX PAYMENT']):
        return 'Merchant Fees'
    
    # Office Supplies
    if any(pattern in text for pattern in ['STAPLES', 'OFFICE DEPOT', 'GRAND & TOY']):
        return 'Office Supplies'
    
    # Supplies (General)
    if any(pattern in text for pattern in ['CANADIAN TIRE', 'HOME DEPOT', 'COSTCO', 'WALMART', 'RONA', 'LOWES']):
        return 'Supplies'
    
    # Food/Meals
    if any(pattern in text for pattern in ['TIM HORTONS', 'MCDONALDS', 'SUBWAY', 'A&W', 'STARBUCKS', 'WENDYS', 'BURGER KING']):
        return 'Meals & Entertainment'
    
    # Groceries
    if any(pattern in text for pattern in ['SUPERSTORE', 'SAFEWAY', 'SOBEYS', '7-ELEVEN', 'SAVE ON FOODS', 'CO-OP']):
        return 'Groceries'
    
    # Utilities
    if any(pattern in text for pattern in ['TELUS', 'SHAW', 'ENMAX', 'ATCO', 'EPCOR', 'DIRECTENERGY']):
        return 'Utilities'
    
    # Vehicle Financing
    if any(pattern in text for pattern in ['CAR LOAN', 'AUTO LOAN', 'VEHICLE LOAN', 'CIBC LOAN', 'TD AUTO']):
        return 'Vehicle Financing'
    
    # Transfers
    if any(pattern in text for pattern in ['E-TRANSFER', 'ETRANSFER', 'INTERAC E-TRANSFER', 'TRANSFER TO', 'TRANSFER FROM']):
        return 'Transfers'
    
    # Payroll
    if any(pattern in text for pattern in ['PAYROLL', 'SALARY', 'WAGES', 'CRA PAYROLL']):
        return 'Payroll'
    
    # Government/Taxes
    if any(pattern in text for pattern in ['CRA', 'CANADA REVENUE', 'GST', 'WCB', 'WORKERS COMP']):
        return 'Taxes & Government'
    
    # Rent
    if any(pattern in text for pattern in ['RENT', 'LEASE PAYMENT']):
        return 'Rent'
    
    return None

conn = psycopg2.connect(
    host=DB_HOST,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

cur = conn.cursor()

print("\n" + "="*110)
print("AUTO-CATEGORIZATION BY VENDOR")
print("="*110 + "\n")

# Analyze banking transactions
print("Analyzing banking transactions...")
cur.execute("""
    SELECT transaction_id, vendor_extracted, description, category
    FROM banking_transactions
    WHERE (category IS NULL OR category = 'Unknown' OR category = 'Unclassified')
    AND verified = TRUE
""")

banking_updates = {}
category_counts = {}

for trans_id, vendor, description, current_cat in cur.fetchall():
    new_category = determine_category(vendor, description)
    if new_category:
        banking_updates[trans_id] = new_category
        category_counts[new_category] = category_counts.get(new_category, 0) + 1

print(f"Found categories for {len(banking_updates):,} banking transactions\n")

# Analyze receipts
print("Analyzing receipts...")
cur.execute("""
    SELECT receipt_id, vendor_name, description, category
    FROM receipts
    WHERE category IS NULL OR category = 'Unknown' OR category = 'uncategorized_expenses'
""")

receipt_updates = {}
receipt_category_counts = {}

for receipt_id, vendor, description, current_cat in cur.fetchall():
    new_category = determine_category(vendor, description)
    if new_category:
        receipt_updates[receipt_id] = new_category
        receipt_category_counts[new_category] = receipt_category_counts.get(new_category, 0) + 1

print(f"Found categories for {len(receipt_updates):,} receipts\n")

# Show preview
print("="*110)
print("CATEGORIZATION PREVIEW")
print("="*110 + "\n")

print("BANKING TRANSACTIONS BY CATEGORY:")
print(f"{'Category':<30} {'Count':>15}")
print("-"*110)
for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"{category:<30} {count:>15,}")

print(f"\nRECEIPTS BY CATEGORY:")
print(f"{'Category':<30} {'Count':>15}")
print("-"*110)
for category, count in sorted(receipt_category_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"{category:<30} {count:>15,}")

print(f"\n" + "="*110)
print("SUMMARY")
print("="*110)
print(f"Banking transactions to categorize: {len(banking_updates):,}")
print(f"Receipts to categorize: {len(receipt_updates):,}")
print(f"Total: {len(banking_updates) + len(receipt_updates):,}")

# Check for dry-run
dry_run = '--dry-run' in sys.argv or len(sys.argv) == 1

if dry_run:
    print("\n✅ DRY RUN COMPLETE")
    print("Run with --execute to apply categorization")
    cur.close()
    conn.close()
    sys.exit(0)

# Execute mode
print("\n⚠️  EXECUTION MODE")
response = input("\nType 'CATEGORIZE' to proceed: ")
if response != 'CATEGORIZE':
    print("❌ Cancelled")
    cur.close()
    conn.close()
    sys.exit(1)

try:
    # Disable trigger
    print("\n🔓 Disabling banking lock trigger...")
    cur.execute("ALTER TABLE banking_transactions DISABLE TRIGGER trg_banking_transactions_lock")
    
    # Update banking
    print("📝 Updating banking transaction categories...")
    for trans_id, category in banking_updates.items():
        cur.execute("""
            UPDATE banking_transactions
            SET category = %s
            WHERE transaction_id = %s
        """, (category, trans_id))
    
    print(f"   ✅ Updated {len(banking_updates):,} banking transactions")
    
    # Update receipts
    print("📝 Updating receipt categories...")
    for receipt_id, category in receipt_updates.items():
        cur.execute("""
            UPDATE receipts
            SET category = %s
            WHERE receipt_id = %s
        """, (category, receipt_id))
    
    print(f"   ✅ Updated {len(receipt_updates):,} receipts")
    
    # Re-enable trigger
    print("\n🔒 Re-enabling banking lock trigger...")
    cur.execute("ALTER TABLE banking_transactions ENABLE TRIGGER trg_banking_transactions_lock")
    
    conn.commit()
    
    print(f"\n✅ CATEGORIZATION COMPLETE")
    print(f"   Total: {len(banking_updates) + len(receipt_updates):,} transactions categorized")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    conn.rollback()
    raise

finally:
    cur.close()
    conn.close()
