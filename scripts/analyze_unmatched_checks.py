#!/usr/bin/env python3
"""
Analyze unmatched check transactions from Scotia 2012.
Group by amount patterns and description patterns to identify likely categories.
"""

import psycopg2
import os
from collections import defaultdict
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 120)
    print("UNMATCHED CHECK ANALYSIS - Scotia 2012")
    print("=" * 120)
    
    # Get unmatched check transactions
    cur.execute("""
        WITH matched_txns AS (
            SELECT DISTINCT 
                CAST(SUBSTRING(r.source_reference FROM 'banking_([0-9]+)') AS INTEGER) as transaction_id
            FROM receipts r
            WHERE r.source_reference LIKE 'banking_%'
        )
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.debit_amount,
            bt.description,
            bt.category
        FROM banking_transactions bt
        LEFT JOIN matched_txns mt ON bt.transaction_id = mt.transaction_id
        WHERE bt.account_number = '903990106011'
          AND EXTRACT(YEAR FROM bt.transaction_date) = 2012
          AND bt.debit_amount > 0
          AND mt.transaction_id IS NULL
          AND bt.description LIKE '%CHQ%'
        ORDER BY bt.debit_amount DESC
    """)
    
    checks = cur.fetchall()
    
    print(f"\nTotal Unmatched Checks: {len(checks)}")
    print(f"Total Amount: ${sum(c[2] for c in checks):,.2f}")
    
    # Group by amount ranges
    amount_groups = defaultdict(list)
    for check in checks:
        txn_id, date, amount, desc, cat = check
        if amount < 100:
            amount_groups['< $100'].append(check)
        elif amount < 500:
            amount_groups['$100-$500'].append(check)
        elif amount < 1000:
            amount_groups['$500-$1,000'].append(check)
        elif amount < 5000:
            amount_groups['$1,000-$5,000'].append(check)
        else:
            amount_groups['>= $5,000'].append(check)
    
    print("\n" + "=" * 120)
    print("CHECKS BY AMOUNT RANGE")
    print("=" * 120)
    
    for range_name in ['< $100', '$100-$500', '$500-$1,000', '$1,000-$5,000', '>= $5,000']:
        if range_name in amount_groups:
            group = amount_groups[range_name]
            total_amt = sum(c[2] for c in group)
            print(f"\n{range_name}: {len(group)} checks, ${total_amt:,.2f}")
            
            # Show first 5 examples
            print(f"  {'Date':<12} {'Amount':>12} {'Description':<80}")
            print(f"  {'-'*12} {'-'*12} {'-'*80}")
            for check in group[:5]:
                txn_id, date, amount, desc, cat = check
                desc_short = desc[:80] if desc else ""
                print(f"  {date} ${amount:>10,.2f} {desc_short}")
            
            if len(group) > 5:
                print(f"  ... and {len(group) - 5} more")
    
    # Analyze check number patterns
    print("\n" + "=" * 120)
    print("CHECK NUMBER PATTERNS")
    print("=" * 120)
    
    check_numbers = defaultdict(list)
    for check in checks:
        txn_id, date, amount, desc, cat = check
        # Extract check number if present
        if 'CHQ' in desc:
            # Try to extract number after CHQ
            parts = desc.split('CHQ')
            if len(parts) > 1:
                num_part = parts[1].strip().split()[0]
                try:
                    check_num = int(''.join(c for c in num_part if c.isdigit()))
                    check_numbers[check_num].append(check)
                except:
                    pass
    
    if check_numbers:
        print(f"\nFound check numbers for {len(check_numbers)} checks")
        print(f"Check number range: {min(check_numbers.keys())} - {max(check_numbers.keys())}")
        
        # Show some examples
        print(f"\n  {'Check #':>10} {'Date':<12} {'Amount':>12} {'Description':<70}")
        print(f"  {'-'*10} {'-'*12} {'-'*12} {'-'*70}")
        
        for check_num in sorted(check_numbers.keys())[:10]:
            for check in check_numbers[check_num]:
                txn_id, date, amount, desc, cat = check
                desc_short = desc[:70] if desc else ""
                print(f"  {check_num:>10} {date} ${amount:>10,.2f} {desc_short}")
    
    # Analyze description patterns
    print("\n" + "=" * 120)
    print("COMMON DESCRIPTION PATTERNS")
    print("=" * 120)
    
    desc_patterns = defaultdict(list)
    for check in checks:
        txn_id, date, amount, desc, cat = check
        # Extract first few words as pattern
        if desc:
            words = desc.split()[:3]
            pattern = ' '.join(words)
            desc_patterns[pattern].append(check)
    
    # Sort by frequency
    sorted_patterns = sorted(desc_patterns.items(), key=lambda x: len(x[1]), reverse=True)
    
    print(f"\nTop 10 description patterns:")
    print(f"  {'Pattern':<40} {'Count':>10} {'Total Amount':>20}")
    print(f"  {'-'*40} {'-'*10} {'-'*20}")
    
    for pattern, checks_list in sorted_patterns[:10]:
        count = len(checks_list)
        total = sum(c[2] for c in checks_list)
        print(f"  {pattern:<40} {count:>10} ${total:>18,.2f}")
    
    # Monthly distribution
    print("\n" + "=" * 120)
    print("MONTHLY DISTRIBUTION")
    print("=" * 120)
    
    monthly = defaultdict(lambda: {'count': 0, 'amount': Decimal(0)})
    for check in checks:
        txn_id, date, amount, desc, cat = check
        month_key = date.strftime('%Y-%m')
        monthly[month_key]['count'] += 1
        monthly[month_key]['amount'] += amount
    
    print(f"  {'Month':<10} {'Count':>10} {'Total Amount':>20}")
    print(f"  {'-'*10} {'-'*10} {'-'*20}")
    
    for month in sorted(monthly.keys()):
        count = monthly[month]['count']
        amount = monthly[month]['amount']
        print(f"  {month:<10} {count:>10} ${amount:>18,.2f}")
    
    # Recommendations
    print("\n" + "=" * 120)
    print("RECOMMENDATIONS")
    print("=" * 120)
    
    print("\n1. CHECK REGISTER REQUIRED:")
    print("   - Physical check register or check imaging from bank")
    print("   - Would provide: payee names, purpose, authorization")
    
    print("\n2. LIKELY CHECK CATEGORIES (based on amounts):")
    if '< $100' in amount_groups:
        print(f"   - Small checks (< $100): {len(amount_groups['< $100'])} checks - likely supplies, petty expenses")
    if '$100-$500' in amount_groups:
        print(f"   - Medium checks ($100-$500): {len(amount_groups['$100-$500'])} checks - likely contractor payments, utilities")
    if '$1,000-$5,000' in amount_groups:
        print(f"   - Large checks ($1K-$5K): {len(amount_groups['$1,000-$5,000'])} checks - likely owner draws, major expenses")
    if '>= $5,000' in amount_groups:
        print(f"   - Very large checks (>= $5K): {len(amount_groups['>= $5,000'])} checks - likely owner draws, tax payments")
    
    print("\n3. IMMEDIATE ACTIONS:")
    print("   - Request check imaging from Scotia Bank (if available)")
    print("   - Search for physical check register/ledger")
    print("   - Cross-reference with accounting software (QuickBooks) check register")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
