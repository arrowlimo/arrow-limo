#!/usr/bin/env python3
"""
Analyze Scotia Dec 2013 data sources to understand:
1. What's currently in database (QuickBooks data)
2. What's in STATEMENT_TRANSACTIONS list (bank statement data)
3. How to blend vendor/category info from QB with statement transactions
4. Check for backwards dating issues
"""

import os
import sys
import psycopg2
from datetime import datetime
from collections import defaultdict

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

# Load STATEMENT_TRANSACTIONS from import script
STATEMENT_TRANSACTIONS = [
    # December 2
    ('2013-12-02', 'Overdrawn Handling Chg.', 5.00, None),
    ('2013-12-02', 'Returned Cheque - NSF', 2695.40, None),
    ('2013-12-02', 'Returned Cheque - NSF', 889.87, None),
    ('2013-12-02', 'Returned Cheque - NSF', 398.33, None),
    ('2013-12-02', 'Returned Cheque - NSF', 0.30, None),
    ('2013-12-02', 'Miscellaneous Payment PAYMENTECH CA MCARD FEE DR', None, 398.33),
    ('2013-12-02', 'Miscellaneous Payment PAYMENTECH CA DEBITCD FEE DR', None, 0.30),
    ('2013-12-02', 'Rent/Lease HEFFNER AUTO FC', 889.87, None),
    ('2013-12-02', 'Rent/Lease ACE TRUCK RENTALS LTD.', 2695.40, None),
    ('2013-12-02', 'Merchant Deposit Debit 566756800000 00001 VISA', 418.86, None),
    ('2013-12-02', 'Miscellaneous Payment AMEX BANK OF CANADA', None, 1044.37),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 1950.90),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 616.46),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 939.69),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 234.85),
    # ... (abbreviated for analysis, full list in import script)
]

def main():
    print("\n" + "="*80)
    print("SCOTIA BANK DEC 2013 DATA SOURCE ANALYSIS")
    print("="*80)
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get current database data
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            vendor_extracted,
            category,
            source_file,
            created_at
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
        ORDER BY transaction_date, transaction_id
    """)
    
    db_transactions = cur.fetchall()
    
    print(f"\n1. DATABASE (Current QuickBooks data):")
    print(f"   Total transactions: {len(db_transactions)}")
    
    if len(db_transactions) > 0:
        print(f"   Date range: {db_transactions[0][1]} to {db_transactions[-1][1]}")
        print(f"   Created at: {db_transactions[0][8]}")
        
        # Check for vendor_extracted
        with_vendor = sum(1 for t in db_transactions if t[5])
        with_category = sum(1 for t in db_transactions if t[6])
        
        print(f"   With vendor_extracted: {with_vendor} ({with_vendor/len(db_transactions)*100:.1f}%)")
        print(f"   With category: {with_category} ({with_category/len(db_transactions)*100:.1f}%)")
        
        # Show sample
        print("\n   Sample QB transactions (first 5):")
        for i, (txn_id, date, desc, debit, credit, vendor, cat, source, created) in enumerate(db_transactions[:5]):
            amount = debit if debit else credit
            direction = 'DR' if debit else 'CR'
            print(f"     {date} | {direction} ${amount:>10.2f} | Vendor: {vendor or '(none)':<20} | Cat: {cat or '(none)':<15} | {desc[:40]}")
    
    # Analyze statement transactions
    print(f"\n2. BANK STATEMENT (Raw statement data):")
    print(f"   Total transactions: {len(STATEMENT_TRANSACTIONS)}")
    
    stmt_debits = sum(t[2] for t in STATEMENT_TRANSACTIONS if t[2])
    stmt_credits = sum(t[3] for t in STATEMENT_TRANSACTIONS if t[3])
    
    print(f"   Total debits: ${stmt_debits:,.2f}")
    print(f"   Total credits: ${stmt_credits:,.2f}")
    
    # Check for vendor info in statement descriptions
    vendor_patterns = defaultdict(int)
    for date, desc, debit, credit in STATEMENT_TRANSACTIONS:
        if 'HEFFNER' in desc.upper():
            vendor_patterns['HEFFNER'] += 1
        elif 'ACE TRUCK' in desc.upper():
            vendor_patterns['ACE TRUCK'] += 1
        elif 'AMEX' in desc.upper():
            vendor_patterns['AMEX'] += 1
        elif desc.startswith('Cheque'):
            vendor_patterns['Cheque (no vendor)'] += 1
        elif 'Merchant Deposit' in desc:
            vendor_patterns['Merchant Deposit'] += 1
        elif 'POS Purchase' in desc:
            # Extract vendor from POS purchase
            parts = desc.split('POS Purchase ')
            if len(parts) > 1:
                vendor_name = parts[1].split(' ')[0]
                vendor_patterns[f'POS: {vendor_name}'] += 1
    
    print("\n   Vendor patterns in statement:")
    for vendor, count in sorted(vendor_patterns.items(), key=lambda x: -x[1]):
        print(f"     {vendor:<30} {count:>3} transactions")
    
    # Compare DB vs Statement
    print(f"\n3. COMPARISON:")
    db_total = len(db_transactions)
    stmt_total = len(STATEMENT_TRANSACTIONS)
    
    print(f"   Database: {db_total} transactions")
    print(f"   Statement: {stmt_total} transactions")
    print(f"   Difference: {stmt_total - db_total} transactions")
    
    if stmt_total > db_total:
        print(f"\n   [ANALYSIS] Bank statement has {stmt_total - db_total} MORE transactions than QB")
        print(f"   This means QuickBooks is missing {stmt_total - db_total} transactions")
        print(f"   RECOMMENDATION: Import statement transactions, use QB vendor/category where available")
    
    # Check for backwards dating
    print(f"\n4. BACKWARDS DATING CHECK:")
    
    if len(db_transactions) > 0:
        created_at = db_transactions[0][8]
        first_txn_date = db_transactions[0][1]
        last_txn_date = db_transactions[-1][1]
        
        print(f"   First transaction date: {first_txn_date}")
        print(f"   Last transaction date: {last_txn_date}")
        print(f"   Database import date: {created_at}")
        
        # Check if created_at is BEFORE transaction dates (backwards dating)
        if created_at.date() < first_txn_date:
            print(f"\n   [WARNING] Import date ({created_at.date()}) is BEFORE transaction dates!")
            print(f"   This indicates BACKWARDS DATING - data was imported retroactively")
        elif created_at.date() < last_txn_date:
            print(f"\n   [INFO] Import date is between first and last transaction dates (normal)")
        else:
            print(f"\n   [INFO] Import date is AFTER transaction dates (typical retrospective import)")
    
    # Matching strategy
    print(f"\n5. BLENDING STRATEGY:")
    print(f"   STEP 1: Match statement transactions to QB by (date, amount)")
    print(f"   STEP 2: For matches, use QB vendor_extracted and category")
    print(f"   STEP 3: For unmatched statement transactions, extract vendor from description")
    print(f"   STEP 4: Categorize using transaction type patterns")
    print(f"   STEP 5: Import blended data with source tracking")
    
    # Build matching lookup
    db_lookup = defaultdict(list)
    for txn_id, date, desc, debit, credit, vendor, cat, source, created in db_transactions:
        amount = debit if debit else credit
        key = (str(date), float(amount) if amount else 0)
        db_lookup[key].append({
            'id': txn_id,
            'description': desc,
            'vendor': vendor,
            'category': cat,
            'debit': debit,
            'credit': credit
        })
    
    # Match statement to QB
    matched = 0
    unmatched = []
    
    for stmt_date, stmt_desc, stmt_debit, stmt_credit in STATEMENT_TRANSACTIONS:
        stmt_amount = stmt_debit if stmt_debit else stmt_credit
        key = (stmt_date, float(stmt_amount))
        
        if key in db_lookup:
            matched += 1
        else:
            unmatched.append((stmt_date, stmt_desc, stmt_debit, stmt_credit))
    
    print(f"\n6. MATCHING RESULTS:")
    print(f"   Matched (QB + Statement): {matched} transactions")
    print(f"   Unmatched (Statement only): {len(unmatched)} transactions")
    print(f"   Match rate: {matched/len(STATEMENT_TRANSACTIONS)*100:.1f}%")
    
    if len(unmatched) > 0:
        print(f"\n   Sample unmatched statement transactions:")
        for date, desc, debit, credit in unmatched[:10]:
            amount = debit if debit else credit
            direction = 'DR' if debit else 'CR'
            print(f"     {date} | {direction} ${amount:>10.2f} | {desc[:60]}")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)
    print("NEXT STEPS:")
    print("="*80)
    print("1. Create blended import script that:")
    print("   - Matches statement to QB by (date, amount)")
    print("   - Uses QB vendor/category for matched transactions")
    print("   - Extracts vendor from description for unmatched")
    print("   - Applies intelligent categorization")
    print("2. Delete current 92 QB transactions (incomplete)")
    print("3. Import full blended dataset (160 transactions)")
    print("="*80)

if __name__ == '__main__':
    main()
