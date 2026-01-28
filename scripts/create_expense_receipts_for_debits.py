#!/usr/bin/env python3
"""
Create expense receipts for all banking debit transactions that don't have receipts.

This creates receipts with:
- expense column populated (amount)
- GL codes based on transaction type
- gst_exempt flag set appropriately
- Notes indicating auto-created from banking
"""

import psycopg2
import hashlib
from datetime import datetime
from decimal import Decimal

# Dry run mode
DRY_RUN = False

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

print("=" * 80)
print("CREATE EXPENSE RECEIPTS FOR MISSING DEBIT TRANSACTIONS")
print("=" * 80)
print(f"\nMode: {'DRY RUN (no changes)' if DRY_RUN else 'LIVE (will insert)'}")
print("=" * 80)

# Get all debit transactions without receipts
cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.account_number,
        bt.transaction_date,
        bt.description,
        bt.debit_amount
    FROM banking_transactions bt
    WHERE bt.debit_amount > 0
      AND NOT EXISTS (
          SELECT 1 FROM receipts r 
          WHERE r.banking_transaction_id = bt.transaction_id
      )
    ORDER BY bt.transaction_date, bt.transaction_id
""")

transactions = cur.fetchall()

print(f"\n📊 Found {len(transactions):,} debit transactions without receipts")
print(f"   Total amount: ${sum(t[4] for t in transactions):,.2f}")

# Categorize transactions and assign GL codes
def categorize_transaction(description, account_number):
    """Assign GL code and vendor name based on transaction description."""
    desc_upper = description.upper()
    
    # NSF charges (bank fees for returned payments)
    if 'NSF' in desc_upper or 'INSUFFICIENT' in desc_upper:
        return {
            'vendor': 'NSF CHARGE',
            'gl_code': '6800',  # Bank Charges
            'gl_name': 'NSF Charges',
            'gst_exempt': True,
            'category': 'NSF Charge'
        }
    
    # Bank fees and charges
    if any(word in desc_upper for word in ['SERVICE CHARGE', 'BANK FEE', 'ACCOUNT FEE', 'MONTHLY FEE', 'OVERDRAFT']):
        return {
            'vendor': 'BANK CHARGES',
            'gl_code': '6800',
            'gl_name': 'Bank Service Charges',
            'gst_exempt': True,
            'category': 'Bank Fee'
        }
    
    # Transfers out
    if 'TRANSFER' in desc_upper:
        return {
            'vendor': 'BANK TRANSFER',
            'gl_code': '1000',
            'gl_name': 'Inter-Account Transfer',
            'gst_exempt': True,
            'category': 'Transfer'
        }
    
    # Loan payments
    if 'LOAN PAYMENT' in desc_upper or 'HEFFNER' in desc_upper:
        return {
            'vendor': 'LOAN PAYMENT',
            'gl_code': '2500',
            'gl_name': 'Loan Payments',
            'gst_exempt': True,
            'category': 'Loan Payment'
        }
    
    # Withdrawals (owner draws)
    if 'WITHDRAWAL' in desc_upper or 'ATM' in desc_upper or 'ABM' in desc_upper:
        return {
            'vendor': 'OWNER WITHDRAWAL',
            'gl_code': '3100',
            'gl_name': 'Owner Draws',
            'gst_exempt': True,
            'category': 'Owner Draw'
        }
    
    # Card/Interac purchases
    if any(word in desc_upper for word in ['INTERAC', 'DEBIT CARD', 'POINT OF SALE', 'POS']):
        return {
            'vendor': 'CARD PURCHASE',
            'gl_code': '6000',
            'gl_name': 'Operating Expenses',
            'gst_exempt': False,
            'category': 'Card Purchase'
        }
    
    # Default: unclassified expense
    return {
        'vendor': 'UNCLASSIFIED EXPENSE',
        'gl_code': '6000',
        'gl_name': 'Operating Expenses',
        'gst_exempt': False,
        'category': 'Other Expense'
    }

# Categorize all transactions
categorized = []
category_stats = {}

for txn_id, account, date, description, amount in transactions:
    cat = categorize_transaction(description, account)
    cat['transaction_id'] = txn_id
    cat['account'] = account
    cat['date'] = date
    cat['description'] = description
    cat['amount'] = amount
    categorized.append(cat)
    
    category_key = cat['category']
    if category_key not in category_stats:
        category_stats[category_key] = {'count': 0, 'amount': Decimal(0)}
    category_stats[category_key]['count'] += 1
    category_stats[category_key]['amount'] += amount

# Show categorization summary
print("\n" + "=" * 80)
print("CATEGORIZATION SUMMARY")
print("=" * 80)
print(f"\n{'Category':<25s} | {'Count':>8s} | {'Total Amount':>15s} | GL Code | GST Exempt")
print("-" * 85)

for category in sorted(category_stats.keys()):
    stats = category_stats[category]
    sample = next(c for c in categorized if c['category'] == category)
    exempt_text = "Yes" if sample['gst_exempt'] else "No"
    print(f"{category:<25s} | {stats['count']:>8,d} | ${stats['amount']:>14,.2f} | {sample['gl_code']:>7s} | {exempt_text:>10s}")

# Show samples
print("\n" + "=" * 80)
print("SAMPLE RECEIPTS TO BE CREATED (first 10)")
print("=" * 80)
print(f"\n{'Date':<12s} | {'Vendor':<25s} | {'Amount':>10s} | GL Code | {'Bank Description':<40s}")
print("-" * 110)

for cat in categorized[:10]:
    print(f"{cat['date']} | {cat['vendor']:<25s} | ${cat['amount']:>9.2f} | {cat['gl_code']:>7s} | {cat['description'][:40]}")

if DRY_RUN:
    print("\n" + "=" * 80)
    print("DRY RUN COMPLETE - No receipts created")
    print("=" * 80)
    print(f"\nTo create these {len(categorized):,} expense receipts, edit this script:")
    print("  Change: DRY_RUN = False")
    print("  Then run again")
else:
    # Create receipts
    print("\n" + "=" * 80)
    print("CREATING RECEIPTS...")
    print("=" * 80)
    
    created_count = 0
    for cat in categorized:
        # Generate source hash
        hash_input = f"{cat['transaction_id']}_{cat['date']}_{cat['amount']}_expense_receipt"
        source_hash = hashlib.sha256(hash_input.encode()).hexdigest()
        
        cur.execute("""
            INSERT INTO receipts (
                receipt_date,
                vendor_name,
                description,
                gross_amount,
                expense,
                revenue,
                gst_exempt,
                gl_account_code,
                gl_account_name,
                created_from_banking,
                banking_transaction_id,
                source_hash,
                source_system,
                validation_status,
                comment,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            cat['date'],
            cat['vendor'],
            cat['description'][:255],
            cat['amount'],
            cat['amount'],  # expense = gross_amount
            0,  # revenue = 0
            cat['gst_exempt'],
            cat['gl_code'],
            cat['gl_name'],
            True,  # created_from_banking
            cat['transaction_id'],
            source_hash,
            'banking_auto_expense',
            'auto_created',
            f"Auto-created expense receipt from banking transaction. Category: {cat['category']}",
            datetime.now()
        ))
        
        created_count += 1
        if created_count % 100 == 0:
            print(f"  ✓ Created {created_count:,} receipts...")
    
    conn.commit()
    print(f"\n✅ Successfully created {created_count:,} expense receipts")
    print("=" * 80)

cur.close()
conn.close()
