#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fix_null_banking_categories.py

Assign categories to banking transactions with NULL category values
based on description patterns and vendor information.
"""

import psycopg2
import re

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def categorize_from_description(description, vendor, debit, credit):
    """Determine category from transaction description and vendor."""
    if not description:
        description = ""
    
    desc_upper = description.upper()
    vendor_upper = (vendor or "").upper()
    
    # Deposits and income
    if credit and credit > 0:
        if any(x in desc_upper for x in ['DEPOSIT', 'VCARD', 'MCARD', 'ACARD', 'DCARD']):
            return 'Income - Card Payments'
        if 'TRANSFER' in desc_upper and 'FROM' in desc_upper:
            return 'Transfer In'
        if any(x in desc_upper for x in ['E-TRANSFER', 'EMAIL TRANSFER', 'INTERAC']):
            return 'Income - Email Transfer'
        return 'Income - Other'
    
    # Debits - expenses
    if debit and debit > 0:
        # Fuel
        if any(x in vendor_upper for x in ['FAS GAS', 'SHELL', 'PETRO CANADA', 'ESSO', 'HUSKY', 'CO-OP']):
            return 'Fuel'
        
        # Banking fees
        if any(x in desc_upper for x in ['SERVICE CHARGE', 'MONTHLY FEE', 'NSF', 'OVERDRAFT', 'BANK FEE']):
            return 'Bank Fees'
        
        # Transfers
        if 'TRANSFER' in desc_upper and 'TO' in desc_upper:
            return 'Transfer Out'
        
        # Payroll
        if any(x in desc_upper for x in ['PAYROLL', 'SALARY', 'WAGES', 'DIRECT DEPOSIT']):
            return 'Payroll'
        
        # Tax payments
        if any(x in desc_upper for x in ['CRA', 'REVENUE CANADA', 'TAX', 'GST', 'PAYROLL TAX']):
            return 'Taxes'
        
        # Loan payments
        if any(x in desc_upper for x in ['LOAN PAYMENT', 'VEHICLE LOAN', 'AUTO LOAN', 'FINANCING']):
            return 'Loan Payment'
        
        # Insurance
        if 'INSURANCE' in desc_upper or 'INSURANCE' in vendor_upper:
            return 'Insurance'
        
        # Utilities
        if any(x in desc_upper for x in ['TELUS', 'SHAW', 'ENMAX', 'ATCO', 'DIRECT ENERGY']):
            return 'Utilities'
        
        # Card payments (business expenses)
        if any(x in desc_upper for x in ['CAPITAL ONE', 'MASTERCARD', 'VISA', 'CREDIT CARD']):
            return 'Credit Card Payment'
        
        # Retail/supplies
        if any(x in vendor_upper for x in ['WALMART', 'CANADIAN TIRE', 'HOME DEPOT', 'COSTCO', 'SUPERSTORE']):
            return 'Supplies'
        
        # Food/meals
        if any(x in vendor_upper for x in ['TIM HORTONS', 'MCDONALDS', 'SUBWAY', 'A&W', 'RESTAURANT']):
            return 'Meals & Entertainment'
        
        # Professional services
        if any(x in desc_upper for x in ['LAWYER', 'ACCOUNTANT', 'PROFESSIONAL', 'CONSULTANT']):
            return 'Professional Fees'
        
        # Rent/lease
        if any(x in desc_upper for x in ['RENT', 'LEASE']):
            return 'Rent/Lease'
        
        # Check payments
        if 'CHQ' in desc_upper or 'CHEQUE' in desc_upper or 'CHECK' in desc_upper:
            return 'Check Payment'
        
        # Wire transfers
        if 'WIRE' in desc_upper or 'EFT' in desc_upper:
            return 'Wire Transfer'
        
        # ATM withdrawals
        if 'ATM' in desc_upper or 'WITHDRAWAL' in desc_upper:
            return 'Cash Withdrawal'
        
        # Default for debits
        return 'Expense - Other'
    
    return 'Unknown'

conn = psycopg2.connect(
    host=DB_HOST,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

cur = conn.cursor()

print("\n" + "="*110)
print("FIXING NULL BANKING CATEGORIES")
print("="*110 + "\n")

# Find transactions with NULL categories
print("Checking for NULL categories...")
cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions 
    WHERE category IS NULL
""")

null_count = cur.fetchone()[0]
print(f"Found {null_count:,} transactions with NULL category\n")

if null_count == 0:
    print("✅ No NULL categories found!")
    cur.close()
    conn.close()
    exit(0)

# Get sample transactions with NULL categories
print("Sample transactions with NULL categories:")
print(f"{'Date':<12} {'Description':<60} {'Debit':>12} {'Credit':>12}")
print("-"*110)

cur.execute("""
    SELECT transaction_date, description, 
           debit_amount, credit_amount, vendor_extracted
    FROM banking_transactions
    WHERE category IS NULL
    ORDER BY transaction_date DESC
    LIMIT 20
""")

for date, desc, debit, credit, vendor in cur.fetchall():
    debit_str = f"${debit:,.2f}" if debit else ""
    credit_str = f"${credit:,.2f}" if credit else ""
    print(f"{str(date):<12} {desc[:58]:<60} {debit_str:>12} {credit_str:>12}")

# Categorize all NULL transactions
print(f"\n{'='*110}")
print("CATEGORIZATION PREVIEW")
print("="*110 + "\n")

cur.execute("""
    SELECT transaction_id, description, vendor_extracted, 
           debit_amount, credit_amount
    FROM banking_transactions
    WHERE category IS NULL
""")

categorizations = {}
category_counts = {}

for trans_id, desc, vendor, debit, credit in cur.fetchall():
    category = categorize_from_description(desc, vendor, debit, credit)
    categorizations[trans_id] = category
    category_counts[category] = category_counts.get(category, 0) + 1

# Show category distribution
print(f"{'Category':<40} {'Count':>10}")
print("-"*110)
for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"{category:<40} {count:>10,}")

print(f"\nTotal transactions to categorize: {len(categorizations):,}")

# Apply categorizations
print(f"\n{'='*110}")
response = input("Apply these categorizations? (yes/no): ")

if response.lower() != 'yes':
    print("❌ Cancelled")
    cur.close()
    conn.close()
    exit(0)

try:
    # Disable trigger
    print("\n🔓 Disabling banking lock trigger...")
    cur.execute("ALTER TABLE banking_transactions DISABLE TRIGGER trg_banking_transactions_lock")
    
    print("📝 Applying categories...")
    
    updated = 0
    for trans_id, category in categorizations.items():
        cur.execute("""
            UPDATE banking_transactions
            SET category = %s
            WHERE transaction_id = %s
        """, (category, trans_id))
        updated += cur.rowcount
    
    # Re-enable trigger
    print("🔒 Re-enabling banking lock trigger...")
    cur.execute("ALTER TABLE banking_transactions ENABLE TRIGGER trg_banking_transactions_lock")
    
    conn.commit()
    
    print(f"\n✅ CATEGORIZATION COMPLETE")
    print(f"   Updated {updated:,} transactions")
    
    # Verify no NULLs remain
    cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE category IS NULL")
    remaining = cur.fetchone()[0]
    
    if remaining == 0:
        print(f"   ✅ All banking transactions now have categories!")
    else:
        print(f"   ⚠️  {remaining:,} transactions still have NULL category")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    conn.rollback()
    raise

finally:
    cur.close()
    conn.close()
