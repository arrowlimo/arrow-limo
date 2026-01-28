#!/usr/bin/env python3
"""
Create revenue receipts for all banking credit transactions that don't have receipts.

This creates receipts with:
- revenue column populated (amount)
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
print("CREATE REVENUE RECEIPTS FOR MISSING CREDIT TRANSACTIONS")
print("=" * 80)
print(f"\nMode: {'DRY RUN (no changes)' if DRY_RUN else 'LIVE (will insert)'}")
print("=" * 80)

# Get all credit transactions without receipts
cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.account_number,
        bt.transaction_date,
        bt.description,
        bt.credit_amount
    FROM banking_transactions bt
    WHERE bt.credit_amount > 0
      AND NOT EXISTS (
          SELECT 1 FROM receipts r 
          WHERE r.banking_transaction_id = bt.transaction_id
      )
    ORDER BY bt.transaction_date, bt.transaction_id
""")

transactions = cur.fetchall()

print(f"\n📊 Found {len(transactions):,} credit transactions without receipts")
print(f"   Total amount: ${sum(t[4] for t in transactions):,.2f}")

# Categorize transactions and assign GL codes
def categorize_transaction(description, account_number):
    """Assign GL code and vendor name based on transaction description."""
    desc_upper = description.upper()
    
    # ATM/Cash deposits by owner
    if 'ATM DEPOSIT' in desc_upper or 'ABM DEPOSIT' in desc_upper:
        return {
            'vendor': 'OWNER CASH DEPOSIT',
            'gl_code': '3000',  # Owner's Equity / Capital Contribution
            'gl_name': 'Owner Cash Deposits',
            'gst_exempt': True,  # Owner contributions are GST exempt
            'category': 'Owner Capital'
        }
    
    # Payment reversals (Heffner, EFT reversals)
    if 'REVERSAL' in desc_upper or ('CHEQUE EXPENSE' in desc_upper and 'HEFFNER' in desc_upper):
        return {
            'vendor': 'PAYMENT REVERSAL',
            'gl_code': '1200',  # Accounts Receivable (offset the original expense)
            'gl_name': 'Payment Reversals',
            'gst_exempt': True,  # No GST on reversals
            'category': 'Payment Reversal'
        }
    
    # Customer deposits (most common)
    if any(word in desc_upper for word in ['E-TRANSFER', 'EMAIL TRANSFER', 'INTERAC', 'SQUARE', 'PAYPAL', 'STRIPE']):
        return {
            'vendor': 'CUSTOMER DEPOSITS',
            'gl_code': '4010',  # Revenue - Customer Deposits
            'gl_name': 'Customer Deposits',
            'gst_exempt': False,  # Customer deposits are taxable revenue
            'category': 'Customer Payment'
        }
    
    # Bank interest
    if 'INTEREST' in desc_upper and 'OVERDRAFT' not in desc_upper:
        return {
            'vendor': 'BANK INTEREST',
            'gl_code': '4900',  # Other Income
            'gl_name': 'Interest Income',
            'gst_exempt': True,  # Interest is GST exempt
            'category': 'Interest Income'
        }
    
    # NSF returns (customer payment came back)
    if 'NSF' in desc_upper or 'INSUFFICIENT FUNDS' in desc_upper:
        return {
            'vendor': 'NSF RETURN',
            'gl_code': '1200',  # Accounts Receivable (offset)
            'gl_name': 'NSF Returns',
            'gst_exempt': True,  # No GST on returned payments
            'category': 'NSF Return'
        }
    
    # Loan proceeds
    if 'LOAN' in desc_upper and 'PAYMENT' not in desc_upper:
        return {
            'vendor': 'LOAN PROCEEDS',
            'gl_code': '2500',  # Long Term Liabilities
            'gl_name': 'Loan Proceeds',
            'gst_exempt': True,  # Loans are GST exempt
            'category': 'Loan Proceeds'
        }
    
    # Transfers between accounts
    if 'TRANSFER' in desc_upper:
        return {
            'vendor': 'BANK TRANSFER',
            'gl_code': '1000',  # Cash/Bank
            'gl_name': 'Inter-Account Transfer',
            'gst_exempt': True,  # Transfers are GST exempt
            'category': 'Bank Transfer'
        }
    
    # Refunds
    if 'REFUND' in desc_upper or 'RETURN' in desc_upper:
        return {
            'vendor': 'REFUND',
            'gl_code': '1200',  # Accounts Receivable
            'gl_name': 'Refunds Received',
            'gst_exempt': True,  # Refunds don't have GST
            'category': 'Refund'
        }
    
    # Default: unclassified revenue (generic deposits, credit memos, misc payments)
    return {
        'vendor': 'CUSTOMER DEPOSITS',
        'gl_code': '4010',  # Default to revenue
        'gl_name': 'Customer Deposits - Other',
        'gst_exempt': False,  # Default to taxable
        'category': 'Other Revenue'
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
    print(f"\nTo create these {len(categorized):,} revenue receipts, edit this script:")
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
        hash_input = f"{cat['transaction_id']}_{cat['date']}_{cat['amount']}_revenue_receipt"
        source_hash = hashlib.sha256(hash_input.encode()).hexdigest()
        
        cur.execute("""
            INSERT INTO receipts (
                receipt_date,
                vendor_name,
                description,
                gross_amount,
                revenue,
                expense,
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
            cat['description'][:255],  # Truncate if needed
            cat['amount'],
            cat['amount'],  # revenue = gross_amount for deposits
            0,  # expense = 0
            cat['gst_exempt'],
            cat['gl_code'],
            cat['gl_name'],
            True,  # created_from_banking
            cat['transaction_id'],
            source_hash,
            'banking_auto_revenue',
            'auto_created',
            f"Auto-created revenue receipt from banking transaction. Category: {cat['category']}",
            datetime.now()
        ))
        
        created_count += 1
        if created_count % 100 == 0:
            print(f"  ✓ Created {created_count:,} receipts...")
    
    conn.commit()
    print(f"\n✅ Successfully created {created_count:,} revenue receipts")
    print("=" * 80)

cur.close()
conn.close()
