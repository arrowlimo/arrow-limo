#!/usr/bin/env python
"""
Import Capital One credit card statement - Page 2 transactions (continued).
Additional transactions from Feb 2012 through Jan 2013.
"""

import psycopg2
import os
from datetime import datetime
from decimal import Decimal
import hashlib

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def generate_source_hash(date, vendor, amount, card_last4):
    """Generate deterministic hash for deduplication"""
    key = f"{date}|{vendor}|{amount}|{card_last4}"
    return hashlib.sha256(key.encode()).hexdigest()

def categorize_transaction(vendor, amount, trans_type):
    """Categorize credit card transaction"""
    vendor_lower = vendor.lower()
    
    # Interest charges and fees are always business expenses (cost of credit)
    if trans_type in ['interest', 'fee', 'member_fee']:
        return True, f'Banking - Credit Card {trans_type.title()}'
    
    # Business-related vendors
    if any(x in vendor_lower for x in [
        'arrow limousine', 'm.c limousine', 'limousine',
        'rogers', 'sirius radio',  # Business phone/radio
    ]):
        return True, 'Business Expense'
    
    # Travel expenses - determine by context
    if any(x in vendor_lower for x in ['hertz', 'best western', 'super 8', 'manning motor inn']):
        # These hotels are in business operation areas (Cochrane, Dryden, Swift Current, Manning)
        return True, 'Business Travel - Lodging'
    
    # Default to business
    return True, 'Business Expense'

def calculate_gst(gross_amount, rate=0.05):
    """Calculate GST included in amount"""
    gst = gross_amount * Decimal(rate) / (Decimal('1.0') + Decimal(rate))
    net = gross_amount - gst
    return round(gst, 2), round(net, 2)

def import_statement_transactions(cur, conn, dry_run=True):
    """Import Capital One statement page 2 transactions"""
    
    card_last4 = '9853'
    account_holder = 'Paul D Richard'
    
    # Transactions from statement page 2
    transactions = [
        # February 2012
        {
            'trans_date': datetime(2012, 2, 20).date(),
            'post_date': datetime(2012, 2, 20).date(),
            'vendor': 'Capital One - Interest Charges',
            'amount': Decimal('42.87'),
            'type': 'interest'
        },
        # March 2012
        {
            'trans_date': datetime(2012, 3, 20).date(),
            'post_date': datetime(2012, 3, 20).date(),
            'vendor': 'Capital One - Overlimit Fee',
            'amount': Decimal('29.00'),
            'type': 'fee'
        },
        {
            'trans_date': datetime(2012, 3, 20).date(),
            'post_date': datetime(2012, 3, 20).date(),
            'vendor': 'Capital One - Interest Charges',
            'amount': Decimal('48.00'),
            'type': 'interest'
        },
        # April 2012
        {
            'trans_date': datetime(2012, 4, 20).date(),
            'post_date': datetime(2012, 4, 20).date(),
            'vendor': 'Capital One - Interest Charges',
            'amount': Decimal('20.51'),
            'type': 'interest'
        },
        {
            'trans_date': datetime(2012, 4, 20).date(),
            'post_date': datetime(2012, 4, 21).date(),
            'vendor': 'M.C Limousine and Taxi - High River AB',
            'amount': Decimal('768.00'),
            'type': 'purchase'
        },
        {
            'trans_date': datetime(2012, 4, 25).date(),
            'post_date': datetime(2012, 4, 26).date(),
            'vendor': 'Hertz - Red Deer AB',
            'amount': Decimal('118.13'),
            'type': 'purchase'
        },
        {
            'trans_date': datetime(2012, 4, 30).date(),
            'post_date': datetime(2012, 5, 1).date(),
            'vendor': 'Arrow Limousine - Red Deer AB',
            'amount': Decimal('701.86'),
            'type': 'purchase'
        },
        {
            'trans_date': datetime(2012, 5, 3).date(),
            'post_date': datetime(2012, 5, 4).date(),
            'vendor': 'Rogers - 888-764-3771 ON',
            'amount': Decimal('882.50'),
            'type': 'purchase'
        },
        # May 2012
        {
            'trans_date': datetime(2012, 5, 19).date(),
            'post_date': datetime(2012, 5, 19).date(),
            'vendor': 'Capital One - Overlimit Fee',
            'amount': Decimal('29.00'),
            'type': 'fee'
        },
        {
            'trans_date': datetime(2012, 5, 19).date(),
            'post_date': datetime(2012, 5, 19).date(),
            'vendor': 'Capital One - Interest Charges',
            'amount': Decimal('0.51'),
            'type': 'interest'
        },
        # June 2012
        {
            'trans_date': datetime(2012, 6, 20).date(),
            'post_date': datetime(2012, 6, 20).date(),
            'vendor': 'Capital One - Overlimit Fee',
            'amount': Decimal('29.00'),
            'type': 'fee'
        },
        {
            'trans_date': datetime(2012, 6, 20).date(),
            'post_date': datetime(2012, 6, 20).date(),
            'vendor': 'Capital One - Interest Charges',
            'amount': Decimal('75.70'),
            'type': 'interest'
        },
        # July 2012
        {
            'trans_date': datetime(2012, 7, 20).date(),
            'post_date': datetime(2012, 7, 20).date(),
            'vendor': 'Capital One - Overlimit Fee',
            'amount': Decimal('29.00'),
            'type': 'fee'
        },
        {
            'trans_date': datetime(2012, 7, 20).date(),
            'post_date': datetime(2012, 7, 20).date(),
            'vendor': 'Capital One - Interest Charges',
            'amount': Decimal('45.11'),
            'type': 'interest'
        },
        # August 2012
        {
            'trans_date': datetime(2012, 8, 20).date(),
            'post_date': datetime(2012, 8, 20).date(),
            'vendor': 'Capital One - Interest Charges',
            'amount': Decimal('43.34'),
            'type': 'interest'
        },
        # September 2012
        {
            'trans_date': datetime(2012, 9, 20).date(),
            'post_date': datetime(2012, 9, 20).date(),
            'vendor': 'Capital One - Overlimit Fee',
            'amount': Decimal('29.00'),
            'type': 'fee'
        },
        {
            'trans_date': datetime(2012, 9, 20).date(),
            'post_date': datetime(2012, 9, 20).date(),
            'vendor': 'Capital One - Interest Charges',
            'amount': Decimal('42.84'),
            'type': 'interest'
        },
        # October 2012
        {
            'trans_date': datetime(2012, 10, 20).date(),
            'post_date': datetime(2012, 10, 20).date(),
            'vendor': 'Capital One - Overlimit Fee',
            'amount': Decimal('29.00'),
            'type': 'fee'
        },
        {
            'trans_date': datetime(2012, 10, 20).date(),
            'post_date': datetime(2012, 10, 20).date(),
            'vendor': 'Capital One - Interest Charges',
            'amount': Decimal('44.07'),
            'type': 'interest'
        },
        {
            'trans_date': datetime(2012, 10, 28).date(),
            'post_date': datetime(2012, 10, 29).date(),
            'vendor': 'Best Western Swan Castle - Cochrane ON',
            'amount': Decimal('119.59'),
            'type': 'purchase'
        },
        {
            'trans_date': datetime(2012, 10, 28).date(),
            'post_date': datetime(2012, 10, 29).date(),
            'vendor': 'Best Western Dryden Motor Inn - Dryden ON',
            'amount': Decimal('134.41'),
            'type': 'purchase'
        },
        {
            'trans_date': datetime(2012, 10, 28).date(),
            'post_date': datetime(2012, 10, 30).date(),
            'vendor': 'Super 8 Swift Current - Swift Current SK',
            'amount': Decimal('121.65'),
            'type': 'purchase'
        },
        # December 2012
        {
            'trans_date': datetime(2012, 12, 20).date(),
            'post_date': datetime(2012, 12, 20).date(),
            'vendor': 'Capital One - Interest Charges',
            'amount': Decimal('34.61'),
            'type': 'interest'
        },
        # January 2013
        {
            'trans_date': datetime(2013, 1, 19).date(),
            'post_date': datetime(2013, 1, 19).date(),
            'vendor': 'Capital One - Member Fee',
            'amount': Decimal('59.00'),
            'type': 'member_fee'
        },
        {
            'trans_date': datetime(2013, 1, 19).date(),
            'post_date': datetime(2013, 1, 19).date(),
            'vendor': 'Capital One - Overlimit Fee',
            'amount': Decimal('29.00'),
            'type': 'fee'
        },
        {
            'trans_date': datetime(2013, 1, 19).date(),
            'post_date': datetime(2013, 1, 19).date(),
            'vendor': 'Capital One - Interest Charges',
            'amount': Decimal('42.36'),
            'type': 'interest'
        },
        {
            'trans_date': datetime(2013, 1, 1).date(),
            'post_date': datetime(2013, 1, 2).date(),
            'vendor': 'Sirius Radio - 888-539-7474 ON',
            'amount': Decimal('210.26'),
            'type': 'purchase'
        },
        {
            'trans_date': datetime(2013, 1, 8).date(),
            'post_date': datetime(2013, 1, 11).date(),
            'vendor': 'Manning Motor Inn - Manning AB',
            'amount': Decimal('102.46'),
            'type': 'purchase'
        },
        {
            'trans_date': datetime(2013, 1, 20).date(),
            'post_date': datetime(2013, 1, 20).date(),
            'vendor': 'Capital One - Member Fee',
            'amount': Decimal('59.00'),
            'type': 'member_fee'
        },
        {
            'trans_date': datetime(2013, 1, 20).date(),
            'post_date': datetime(2013, 1, 20).date(),
            'vendor': 'Capital One - Interest Charges',
            'amount': Decimal('37.90'),
            'type': 'interest'
        }
    ]
    
    print("=" * 80)
    print("CAPITAL ONE STATEMENT PAGE 2 IMPORT")
    print("=" * 80)
    print(f"Account: {account_holder}")
    print(f"Card ending: {card_last4}")
    print(f"Period: Feb 2012 - Jan 2013")
    print(f"Transactions: {len(transactions)}")
    
    # Process each transaction
    print("\n" + "=" * 80)
    print("PROCESSING TRANSACTIONS")
    print("=" * 80)
    
    created_count = 0
    skipped_count = 0
    
    for i, trans in enumerate(transactions, 1):
        vendor = trans['vendor']
        amount = trans['amount']
        trans_date = trans['trans_date']
        trans_type = trans['type']
        
        # Generate hash for deduplication
        source_hash = generate_source_hash(trans_date, vendor, amount, card_last4)
        
        # Check if already exists
        cur.execute("""
            SELECT receipt_id FROM receipts
            WHERE source_hash = %s
        """, (source_hash,))
        
        if cur.fetchone():
            print(f"{i:2d}. SKIP (duplicate) | {trans_date} | {vendor[:50]:50s} | ${amount:>10,.2f}")
            skipped_count += 1
            continue
        
        # Categorize
        is_business, category = categorize_transaction(vendor, amount, trans_type)
        
        # GST calculation (only for purchases, not fees/interest)
        if trans_type == 'purchase' and is_business:
            gst, net = calculate_gst(amount)
        else:
            gst = Decimal('0.00')
            net = amount
        
        description = f"Credit card {trans_type} - Card {card_last4}"
        
        # Create receipt
        if not dry_run:
            business_personal_flag = 'Business' if is_business else 'Personal'
            cur.execute("""
                INSERT INTO receipts (
                    receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
                    description, category, business_personal, 
                    source_reference, source_hash, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (
                trans_date, vendor, amount, gst, net,
                description, category, business_personal_flag,
                f"Capital One {card_last4} - {trans_date}", source_hash
            ))
            created_count += 1
        
        biz_flag = "BIZ" if is_business else "PER"
        print(f"{i:2d}. {biz_flag} | {trans_date} | {vendor[:50]:50s} | ${amount:>10,.2f} | GST: ${gst:>6,.2f}")
    
    if not dry_run:
        conn.commit()
    
    # Summary by category
    print("\n" + "=" * 80)
    print("SUMMARY BY CATEGORY")
    print("=" * 80)
    
    interest_total = sum(t['amount'] for t in transactions if t['type'] == 'interest')
    fee_total = sum(t['amount'] for t in transactions if t['type'] in ['fee', 'member_fee'])
    purchase_total = sum(t['amount'] for t in transactions if t['type'] == 'purchase')
    
    print(f"Interest charges: ${interest_total:,.2f}")
    print(f"Fees (overlimit + member): ${fee_total:,.2f}")
    print(f"Purchases: ${purchase_total:,.2f}")
    print(f"Total charges: ${interest_total + fee_total + purchase_total:,.2f}")
    
    print("\n" + "=" * 80)
    print("IMPORT SUMMARY")
    print("=" * 80)
    print(f"Total transactions: {len(transactions)}")
    print(f"Created: {created_count}")
    print(f"Skipped (duplicates): {skipped_count}")
    
    if dry_run:
        print("\n[WARN] DRY RUN - No changes made to database")
        print("Run with --write to apply changes")
    else:
        print(f"\n[OK] Successfully imported {created_count} transactions")

def main():
    import sys
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    dry_run = '--write' not in sys.argv
    
    try:
        import_statement_transactions(cur, conn, dry_run=dry_run)
    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
