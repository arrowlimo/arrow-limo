#!/usr/bin/env python3
"""
Analyze unmatched credit transactions for Scotia 2012.

Credits are typically:
- Customer deposits (Square, cash, e-transfers)
- Refunds or reversals
- Transfers from other accounts
- Interest income

This script groups by amount, date proximity to charters, and description patterns.
"""

import psycopg2
import os
from datetime import datetime, timedelta
from collections import defaultdict
from decimal import Decimal

def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def analyze_unmatched_credits():
    """Analyze unmatched credit transactions for Scotia 2012."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get unmatched credits (where banking_transaction_id IS NOT NULL but receipt_id IS NULL)
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            credit_amount,
            description
        FROM banking_transactions
        WHERE account_number = '903990106011'
          AND EXTRACT(YEAR FROM transaction_date) = 2012
          AND credit_amount > 0
          AND receipt_id IS NULL
        ORDER BY transaction_date
    """)
    
    credits = cur.fetchall()
    total_amount = sum(Decimal(str(c[2])) for c in credits)
    
    print("=" * 100)
    print(" " * 30 + "UNMATCHED CREDIT ANALYSIS - Scotia 2012")
    print("=" * 100)
    print()
    print(f"Total Unmatched Credits: {len(credits)}")
    print(f"Total Amount: ${total_amount:,.2f}")
    print()
    
    # Group by amount ranges
    print("=" * 100)
    print(" " * 30 + "CREDITS BY AMOUNT RANGE")
    print("=" * 100)
    
    amount_ranges = {
        '< $100': (0, 100),
        '$100-$500': (100, 500),
        '$500-$1,000': (500, 1000),
        '$1,000-$5,000': (1000, 5000),
        '>= $5,000': (5000, float('inf'))
    }
    
    for range_name, (min_amt, max_amt) in amount_ranges.items():
        range_credits = [c for c in credits if min_amt <= c[2] < max_amt]
        range_total = sum(Decimal(str(c[2])) for c in range_credits)
        
        if range_credits:
            print(f"{range_name}: {len(range_credits)} credits, ${range_total:,.2f}")
            print(f"  {'Date':<12} {'Amount':>12} {'Description':<60}")
            print(f"  {'-'*12} {'-'*12} {'-'*60}")
            
            # Show first 5
            for i, (tid, tdate, amt, desc) in enumerate(range_credits[:5]):
                print(f"  {tdate} ${amt:>11,.2f} {desc[:60]}")
            
            if len(range_credits) > 5:
                print(f"  ... and {len(range_credits) - 5} more")
            print()
    
    # Analyze description patterns
    print("=" * 100)
    print(" " * 30 + "COMMON DESCRIPTION PATTERNS")
    print("=" * 100)
    
    # Extract key words from descriptions
    patterns = defaultdict(lambda: {'count': 0, 'total': Decimal('0')})
    
    for tid, tdate, amt, desc in credits:
        desc_upper = desc.upper()
        
        # Categorize by keywords
        if 'SQUARE' in desc_upper or 'SQ *' in desc_upper:
            patterns['Square Payment']['count'] += 1
            patterns['Square Payment']['total'] += Decimal(str(amt))
        elif 'E-TRANSFER' in desc_upper or 'INTERAC' in desc_upper:
            patterns['E-Transfer']['count'] += 1
            patterns['E-Transfer']['total'] += Decimal(str(amt))
        elif 'DEPOSIT' in desc_upper:
            patterns['Deposit']['count'] += 1
            patterns['Deposit']['total'] += Decimal(str(amt))
        elif 'TRANSFER' in desc_upper:
            patterns['Transfer']['count'] += 1
            patterns['Transfer']['total'] += Decimal(str(amt))
        elif 'REFUND' in desc_upper:
            patterns['Refund']['count'] += 1
            patterns['Refund']['total'] += Decimal(str(amt))
        elif 'INTEREST' in desc_upper:
            patterns['Interest']['count'] += 1
            patterns['Interest']['total'] += Decimal(str(amt))
        elif 'REVERSAL' in desc_upper or 'NSF' in desc_upper:
            patterns['NSF/Reversal']['count'] += 1
            patterns['NSF/Reversal']['total'] += Decimal(str(amt))
        else:
            patterns['Other']['count'] += 1
            patterns['Other']['total'] += Decimal(str(amt))
    
    # Sort by total amount
    sorted_patterns = sorted(patterns.items(), key=lambda x: x[1]['total'], reverse=True)
    
    print(f"  {'Pattern':<30} {'Count':>10} {'Total Amount':>20}")
    print(f"  {'-'*30} {'-'*10} {'-'*20}")
    for pattern, data in sorted_patterns:
        print(f"  {pattern:<30} {data['count']:>10} ${data['total']:>18,.2f}")
    print()
    
    # Monthly distribution
    print("=" * 100)
    print(" " * 30 + "MONTHLY DISTRIBUTION")
    print("=" * 100)
    
    monthly = defaultdict(lambda: {'count': 0, 'total': Decimal('0')})
    for tid, tdate, amt, desc in credits:
        month_key = tdate.strftime('%Y-%m')
        monthly[month_key]['count'] += 1
        monthly[month_key]['total'] += Decimal(str(amt))
    
    print(f"  {'Month':>10} {'Count':>10} {'Total Amount':>20}")
    print(f"  {'-'*10} {'-'*10} {'-'*20}")
    for month in sorted(monthly.keys()):
        data = monthly[month]
        print(f"  {month:>10} {data['count']:>10} ${data['total']:>18,.2f}")
    print()
    
    # Analyze date proximity to charters
    print("=" * 100)
    print(" " * 30 + "CHARTER DATE PROXIMITY ANALYSIS")
    print("=" * 100)
    
    # Get all 2012 charter dates and amounts
    cur.execute("""
        SELECT charter_date, paid_amount, total_amount_due
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) = 2012
          AND cancelled = false
        ORDER BY charter_date
    """)
    charter_dates = cur.fetchall()
    
    # For each credit, find nearest charter within +/- 7 days
    near_charter = 0
    potential_deposits = []
    
    for tid, tdate, amt, desc in credits:
        for cdate, paid, total_due in charter_dates:
            if cdate is None:
                continue
            
            days_diff = abs((tdate - cdate).days)
            if days_diff <= 7:
                # Check if amount is close to charter payment
                if paid and abs(float(amt) - float(paid)) < 5.0:
                    near_charter += 1
                    potential_deposits.append((tid, tdate, amt, desc, cdate, paid))
                    break
                elif total_due and abs(float(amt) - float(total_due)) < 5.0:
                    near_charter += 1
                    potential_deposits.append((tid, tdate, amt, desc, cdate, total_due))
                    break
    
    print(f"Credits within 7 days of charter date: {near_charter}")
    print(f"Percentage: {near_charter/len(credits)*100:.1f}%")
    print()
    
    if potential_deposits:
        print("Top 10 potential charter deposits (amount match + date proximity):")
        print(f"  {'Credit Date':<12} {'Amount':>12} {'Charter Date':<12} {'Charter Amt':>12} {'Description':<40}")
        print(f"  {'-'*12} {'-'*12} {'-'*12} {'-'*12} {'-'*40}")
        for tid, tdate, amt, desc, cdate, charter_amt in potential_deposits[:10]:
            print(f"  {tdate} ${amt:>11,.2f} {cdate} ${charter_amt:>11,.2f} {desc[:40]}")
        
        if len(potential_deposits) > 10:
            print(f"  ... and {len(potential_deposits) - 10} more")
        print()
    
    # Recommendations
    print("=" * 100)
    print(" " * 30 + "RECOMMENDATIONS")
    print("=" * 100)
    print("""
1. CUSTOMER DEPOSIT MATCHING:
   - Match credits to charter payment records by amount and date proximity
   - Square payments can be matched using square_transaction_id
   - E-transfers can be matched using reference numbers

2. LIKELY CREDIT CATEGORIES:
   - Square payments: Customer credit card payments for charters
   - E-transfers: Customer deposits via Interac e-Transfer
   - Deposits: Cash deposits from charter payments
   - Transfers: Internal account transfers
   - NSF reversals: Previously bounced checks being returned

3. IMMEDIATE ACTIONS:
   - Create script to match credits to charter payments by amount + date
   - Extract Square transaction IDs from descriptions
   - Match e-transfer reference numbers to charter notes
   - Review "Other" category credits for additional patterns
   
4. CHARTER PAYMENT LINKAGE:
   - {nc} credits ({pct:.1f}%) appear to match charter dates/amounts
   - These are likely customer deposits that should be linked to specific charters
   - Consider creating charter_payment_deposits table to track these relationships
""".format(nc=near_charter, pct=near_charter/len(credits)*100))
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    analyze_unmatched_credits()
