#!/usr/bin/env python3
"""
Analyze unmatched transactions for CIBC account 0228362.
This account has 81.4% match rate - identify patterns in the remaining 18.6%.
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
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def analyze_0228362():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 120)
    print(" " * 35 + "CIBC 0228362 UNMATCHED ANALYSIS")
    print("=" * 120)
    print()
    
    # Get unmatched debits by year
    print("UNMATCHED DEBITS BY YEAR:")
    print(f"{'Year':>6} {'Count':>10} {'Total Amount':>15}")
    print("-" * 35)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year,
            COUNT(*) as cnt,
            SUM(debit_amount) as total
        FROM banking_transactions
        WHERE account_number = '0228362'
          AND debit_amount > 0
          AND receipt_id IS NULL
        GROUP BY EXTRACT(YEAR FROM transaction_date)
        ORDER BY year
    """)
    
    for year, cnt, total in cur.fetchall():
        print(f"{int(year):>6} {cnt:>10} ${total:>13,.2f}")
    print()
    
    # Analyze description patterns for unmatched
    print("DESCRIPTION PATTERNS (Unmatched Debits):")
    print()
    
    patterns = defaultdict(lambda: {'count': 0, 'total': Decimal('0')})
    
    cur.execute("""
        SELECT transaction_date, debit_amount, description
        FROM banking_transactions
        WHERE account_number = '0228362'
          AND debit_amount > 0
          AND receipt_id IS NULL
        ORDER BY transaction_date
    """)
    
    for date, amt, desc in cur.fetchall():
        if not desc or desc == 'nan':
            key = '(blank/nan)'
        elif 'CHEQUE' in desc.upper():
            key = 'CHEQUE'
        elif 'BRANCH' in desc.upper() and 'WITHDRAWAL' in desc.upper():
            key = 'Branch Withdrawal'
        elif 'ABM' in desc.upper() or 'ATM' in desc.upper():
            key = 'ABM/ATM Withdrawal'
        elif 'DEBIT MEMO' in desc.upper():
            key = 'Debit Memo'
        elif 'TRANSFER' in desc.upper():
            key = 'Transfer'
        elif 'FEE' in desc.upper() or 'CHARGE' in desc.upper():
            key = 'Bank Fee/Charge'
        else:
            key = 'Other'
        
        patterns[key]['count'] += 1
        patterns[key]['total'] += Decimal(str(amt))
    
    sorted_patterns = sorted(patterns.items(), key=lambda x: x[1]['total'], reverse=True)
    
    print(f"{'Pattern':<30} {'Count':>10} {'Total Amount':>15}")
    print("-" * 60)
    for pattern, data in sorted_patterns:
        print(f"{pattern:<30} {data['count']:>10} ${data['total']:>13,.2f}")
    print()
    
    # Show samples by pattern
    for pattern_name in ['CHEQUE', 'Branch Withdrawal', 'ABM/ATM Withdrawal', 'Debit Memo']:
        print(f"\nSample {pattern_name} transactions (first 5):")
        print(f"{'Date':<12} {'Amount':>12} {'Description':<70}")
        print("-" * 100)
        
        cur.execute("""
            SELECT transaction_date, debit_amount, description
            FROM banking_transactions
            WHERE account_number = '0228362'
              AND debit_amount > 0
              AND receipt_id IS NULL
              AND description LIKE %s
            ORDER BY transaction_date
            LIMIT 5
        """, (f'%{pattern_name}%',))
        
        for date, amt, desc in cur.fetchall():
            print(f"{date} ${amt:>11,.2f} {desc[:70]}")
    
    # Recommendations
    print("\n" + "=" * 120)
    print(" " * 40 + "RECOMMENDATIONS")
    print("=" * 120)
    print()
    
    print("Account 0228362 has good match rate (81.4%) but remaining transactions include:")
    print()
    print("1. CHEQUES - Likely payroll, contractor payments, owner draws")
    print("   → Need check register or QuickBooks check register")
    print()
    print("2. Branch/ABM Withdrawals - Cash withdrawals")
    print("   → Create 'Cash Withdrawal' receipts (similar to Scotia)")
    print()
    print("3. Debit Memos - CRA payments, fees, adjustments")
    print("   → Create categorized receipts based on description")
    print()
    print("4. Blank/nan descriptions - Data quality issue")
    print("   → Create generic receipts or investigate source data")
    print()
    
    # Get credits analysis
    print("=" * 120)
    print(" " * 35 + "UNMATCHED CREDITS ANALYSIS")
    print("=" * 120)
    print()
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year,
            COUNT(*) as cnt,
            SUM(credit_amount) as total
        FROM banking_transactions
        WHERE account_number = '0228362'
          AND credit_amount > 0
          AND receipt_id IS NULL
        GROUP BY EXTRACT(YEAR FROM transaction_date)
        ORDER BY year
    """)
    
    print(f"{'Year':>6} {'Count':>10} {'Total Amount':>15}")
    print("-" * 35)
    for year, cnt, total in cur.fetchall():
        print(f"{int(year):>6} {cnt:>10} ${total:>13,.2f}")
    print()
    
    print("Sample Unmatched Credits (first 10):")
    print(f"{'Date':<12} {'Amount':>12} {'Description':<70}")
    print("-" * 100)
    
    cur.execute("""
        SELECT transaction_date, credit_amount, description
        FROM banking_transactions
        WHERE account_number = '0228362'
          AND credit_amount > 0
          AND receipt_id IS NULL
        ORDER BY transaction_date
        LIMIT 10
    """)
    
    for date, amt, desc in cur.fetchall():
        print(f"{date} ${amt:>11,.2f} {desc[:70]}")
    print()
    
    print("Credits appear to be:")
    print("  - Electronic Funds Transfers (VISA/MC payments from Global Payments)")
    print("  - Charter customer deposits via credit card processing")
    print("  → Can match to charter payments by amount + date proximity")
    print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    analyze_0228362()
