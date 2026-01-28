#!/usr/bin/env python
"""
Import Capital One credit card statement transactions.
Creates receipts for credit card purchases with proper categorization.
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

def categorize_transaction(vendor, amount):
    """Categorize credit card transaction"""
    vendor_lower = vendor.lower()
    
    # Business vs Personal determination
    if any(x in vendor_lower for x in ['pizza', 'steakhouse', 'hotel', 'vegas', 'show tickets', 't-shirt']):
        is_business = False
        category = 'Personal - Travel/Entertainment'
    else:
        is_business = True
        category = 'Business Expense'
    
    return is_business, category

def calculate_gst(gross_amount, rate=0.05):
    """Calculate GST included in amount"""
    gst = gross_amount * Decimal(rate) / (Decimal('1.0') + Decimal(rate))
    net = gross_amount - gst
    return round(gst, 2), round(net, 2)

def import_statement_transactions(cur, conn, dry_run=True):
    """Import Capital One statement transactions"""
    
    # Statement details
    card_last4 = '9853'
    account_holder = 'Paul D Richard'
    statement_date = datetime(2012, 3, 17).date()  # Due date
    
    # Transactions from statement
    transactions = [
        {
            'trans_date': datetime(2012, 2, 9).date(),
            'post_date': datetime(2012, 2, 9).date(),
            'vendor': 'Capital One - Payment',
            'amount': Decimal('-500.00'),  # Payment (credit)
            'type': 'payment'
        },
        {
            'trans_date': datetime(2012, 2, 10).date(),
            'post_date': datetime(2012, 2, 13).date(),
            'vendor': "George's Pizza & Steakhouse - Red Deer AB",
            'amount': Decimal('48.26'),
            'type': 'purchase'
        },
        {
            'trans_date': datetime(2012, 2, 12).date(),
            'post_date': datetime(2012, 2, 14).date(),
            'vendor': 'Excalibur Show Tickets - Las Vegas NV',
            'amount': Decimal('217.18'),  # USD converted
            'type': 'purchase'
        },
        {
            'trans_date': datetime(2012, 2, 12).date(),
            'post_date': datetime(2012, 2, 14).date(),
            'vendor': 'MGM Grand Hotel - Las Vegas NV',
            'amount': Decimal('91.93'),  # USD converted
            'type': 'purchase'
        },
        {
            'trans_date': datetime(2012, 2, 12).date(),
            'post_date': datetime(2012, 2, 14).date(),
            'vendor': 'MGM Grand Hotel - Las Vegas NV',
            'amount': Decimal('91.93'),  # USD converted (duplicate charge)
            'type': 'purchase'
        },
        {
            'trans_date': datetime(2012, 2, 16).date(),
            'post_date': datetime(2012, 2, 17).date(),
            'vendor': 'T-Shirt Plus - Las Vegas NV',
            'amount': Decimal('100.11'),  # USD converted
            'type': 'purchase'
        },
        {
            'trans_date': datetime(2012, 2, 20).date(),
            'post_date': datetime(2012, 2, 20).date(),
            'vendor': 'Capital One - Overlimit Fee',
            'amount': Decimal('29.00'),
            'type': 'fee'
        }
    ]
    
    print("=" * 80)
    print("CAPITAL ONE STATEMENT IMPORT")
    print("=" * 80)
    print(f"Account: {account_holder}")
    print(f"Card ending: {card_last4}")
    print(f"Statement date: {statement_date}")
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
            print(f"{i:2d}. SKIP (duplicate) | {trans_date} | {vendor[:40]:40s} | ${amount:>10,.2f}")
            skipped_count += 1
            continue
        
        # Categorize
        if trans_type == 'payment':
            is_business = True
            category = 'Credit Card Payment'
            gst = Decimal('0.00')
            net = abs(amount)
            description = f"Capital One payment - Card {card_last4}"
        elif trans_type == 'fee':
            is_business = True
            category = 'Banking - Credit Card Fee'
            gst = Decimal('0.00')
            net = amount
            description = f"Capital One overlimit fee - Card {card_last4}"
        else:
            is_business, category = categorize_transaction(vendor, amount)
            if is_business:
                gst, net = calculate_gst(amount)
            else:
                gst = Decimal('0.00')
                net = amount
            description = f"Credit card purchase - Card {card_last4}"
        
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
                trans_date, vendor, abs(amount), gst, net,
                description, category, business_personal_flag,
                f"Capital One {card_last4} - {trans_date}", source_hash
            ))
            created_count += 1
        
        biz_flag = "BIZ" if is_business else "PER"
        print(f"{i:2d}. {biz_flag} | {trans_date} | {vendor[:40]:40s} | ${amount:>10,.2f} | GST: ${gst:>6,.2f}")
    
    if not dry_run:
        conn.commit()
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total transactions: {len(transactions)}")
    print(f"Created: {created_count}")
    print(f"Skipped (duplicates): {skipped_count}")
    
    if dry_run:
        print("\n[WARN] DRY RUN - No changes made to database")
        print("Run with --write to apply changes")
    else:
        print(f"\n[OK] Successfully imported {created_count} transactions")
        
        # Show statement totals
        total_purchases = sum(t['amount'] for t in transactions if t['type'] == 'purchase')
        total_fees = sum(t['amount'] for t in transactions if t['type'] == 'fee')
        total_payments = sum(abs(t['amount']) for t in transactions if t['type'] == 'payment')
        
        print(f"\nStatement totals:")
        print(f"  Purchases: ${total_purchases:,.2f}")
        print(f"  Fees: ${total_fees:,.2f}")
        print(f"  Payments: -${total_payments:,.2f}")
        print(f"  Net charge: ${total_purchases + total_fees - total_payments:,.2f}")

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
