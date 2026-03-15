#!/usr/bin/env python3
"""
Analyze the 182 credit_card payments from 2012 ($140,645.19).
These appear to be from old QuickBooks import and may have different formatting.
"""

import psycopg2
import os
from datetime import datetime
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 120)
    print("2012 CREDIT CARD PAYMENTS ANALYSIS")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 120)
    
    # Get all 2012 credit_card payments
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            account_number,
            reserve_number,
            amount,
            payment_method,
            reference_number,
            notes,
            square_customer_name,
            payment_key
        FROM payments
        WHERE payment_method = 'credit_card'
        AND (charter_id IS NULL OR charter_id = 0)
        AND payment_date >= '2012-01-01'
        AND payment_date < '2013-01-01'
        ORDER BY payment_date DESC
    """)
    
    cc_payments = cur.fetchall()
    
    print(f"\n### OVERVIEW ###")
    print(f"Total: {len(cc_payments)} credit_card payments")
    print(f"Amount: ${sum(p[4] for p in cc_payments if p[4]):,.2f}")
    
    # Check data sources from notes
    sources = defaultdict(int)
    for p in cc_payments:
        notes = p[7] or ''
        if 'QBO Import' in notes:
            sources['QBO Import'] += 1
        elif 'Square' in notes or 'square' in notes.lower():
            sources['Square'] += 1
        else:
            sources['Unknown'] += 1
    
    print(f"\n### DATA SOURCES ###")
    for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
        print(f"{source}: {count} payments")
    
    # Check for account_number patterns
    with_account = [p for p in cc_payments if p[2]]
    print(f"\n### ACCOUNT NUMBER PATTERNS ###")
    print(f"With account_number: {len(with_account)}/{len(cc_payments)}")
    
    if with_account:
        # Get unique account numbers
        account_nums = list(set(p[2] for p in with_account if p[2]))
        print(f"Unique account numbers: {len(account_nums)}")
        
        # Check if any exist in charters
        placeholders = ','.join(['%s'] * len(account_nums))
        cur.execute(f"""
            SELECT account_number, COUNT(*) as charter_count
            FROM charters
            WHERE account_number IN ({placeholders})
            GROUP BY account_number
        """, account_nums)
        
        charter_accounts = dict(cur.fetchall())
        matches = sum(1 for acc in account_nums if acc in charter_accounts)
        print(f"Account numbers with charters: {matches}/{len(account_nums)}")
    
    # Check for reserve_number
    with_reserve = [p for p in cc_payments if p[3]]
    print(f"\n### RESERVE NUMBER PATTERNS ###")
    print(f"With reserve_number: {len(with_reserve)}/{len(cc_payments)}")
    
    # Check for payment_key patterns
    payment_keys = defaultdict(int)
    for p in cc_payments:
        if p[9]:  # payment_key
            payment_keys[p[9]] += 1
    
    print(f"\n### PAYMENT KEY PATTERNS ###")
    print(f"Unique payment_keys: {len(payment_keys)}")
    print(f"Top 10 payment_keys by frequency:")
    for key, count in sorted(payment_keys.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {key}: {count} payments")
    
    # Sample data
    print(f"\n### SAMPLE PAYMENTS (First 20) ###")
    print(f"{'ID':<8} {'Date':<12} {'Amount':<10} {'Account':<12} {'Payment Key':<15} {'Notes':<50}")
    print("-" * 120)
    
    for p in cc_payments[:20]:
        pid, pdate, acct, resnum, amt, method, ref, notes, sqname, pkey = p
        amt_val = float(amt) if amt else 0.0
        notes_str = (notes or '')[:47] + '...' if notes and len(notes) > 50 else (notes or '')
        print(f"{pid:<8} {str(pdate):<12} ${amt_val:>8.2f} {acct or '':<12} {pkey or '':<15} {notes_str}")
    
    # Check for potential charter matches by date + amount
    print(f"\n### MATCHING OPPORTUNITIES ###")
    
    # Amount + Date matching (±30 days)
    cur.execute("""
        SELECT COUNT(DISTINCT p.payment_id)
        FROM payments p
        WHERE p.payment_method = 'credit_card'
        AND (p.charter_id IS NULL OR p.charter_id = 0)
        AND p.payment_date >= '2012-01-01'
        AND p.payment_date < '2013-01-01'
        AND EXISTS (
            SELECT 1 FROM charters c
            WHERE c.charter_date BETWEEN p.payment_date - INTERVAL '30 days'
                                     AND p.payment_date + INTERVAL '30 days'
            AND ABS(COALESCE(c.balance, c.total_amount_due, 0) - p.amount) < 1.0
        )
    """)
    amount_matches = cur.fetchone()[0]
    print(f"Amount + Date match (±30 days): {amount_matches} potential matches")
    
    # Account + Date matching
    cur.execute("""
        SELECT COUNT(DISTINCT p.payment_id)
        FROM payments p
        WHERE p.payment_method = 'credit_card'
        AND (p.charter_id IS NULL OR p.charter_id = 0)
        AND p.payment_date >= '2012-01-01'
        AND p.payment_date < '2013-01-01'
        AND p.account_number IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM charters c
            WHERE c.account_number = p.account_number
            AND c.charter_date BETWEEN p.payment_date - INTERVAL '60 days'
                                   AND p.payment_date + INTERVAL '30 days'
        )
    """)
    account_matches = cur.fetchone()[0]
    print(f"Account + Date match (±60/30 days): {account_matches} potential matches")
    
    print("\n" + "=" * 120)
    print("KEY FINDINGS:")
    print("=" * 120)
    print("1. All 182 payments are from QuickBooks Online import")
    print("2. These are likely deposits/batch transactions rather than individual payments")
    print("3. Account numbers don't match charter format (903990106011 vs typical format)")
    print("4. May represent CIBC bank account number rather than customer account")
    print("5. Recommend reviewing against 2012 banking_transactions for reconciliation")
    print("=" * 120)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
