#!/usr/bin/env python3
"""
Analyze unmatched transactions in CIBC account 8314462 (88.8% matched).
Identify patterns for banking event creation similar to 0228362 and 3648117.
"""

import psycopg2
from datetime import datetime
from collections import Counter

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("CIBC ACCOUNT 8314462 - UNMATCHED TRANSACTION ANALYSIS")
    print("=" * 80)
    
    # Get account overview
    cur.execute("""
        SELECT 
            COUNT(*) as total_transactions,
            COUNT(CASE WHEN debit_amount > 0 THEN 1 END) as total_debits,
            COUNT(CASE WHEN debit_amount > 0 AND receipt_id IS NULL THEN 1 END) as unmatched_debits,
            SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as total_debit_amount,
            SUM(CASE WHEN debit_amount > 0 AND receipt_id IS NULL THEN debit_amount ELSE 0 END) as unmatched_debit_amount,
            MIN(transaction_date) as earliest_date,
            MAX(transaction_date) as latest_date
        FROM banking_transactions
        WHERE account_number = '8314462'
    """)
    
    row = cur.fetchone()
    total_txns, total_debits, unmatched_debits, total_debit_amt, unmatched_debit_amt, earliest, latest = row
    
    print(f"\nAccount Overview:")
    print(f"  Total transactions: {total_txns:,}")
    print(f"  Total debits: {total_debits:,}")
    print(f"  Unmatched debits: {unmatched_debits:,} ({100*unmatched_debits/total_debits:.1f}%)")
    print(f"  Total debit amount: ${total_debit_amt:,.2f}")
    print(f"  Unmatched debit amount: ${unmatched_debit_amt:,.2f}")
    print(f"  Date range: {earliest} to {latest}")
    
    # Get unmatched transactions by year
    print("\n" + "=" * 80)
    print("UNMATCHED DEBITS BY YEAR")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year,
            COUNT(*) as count,
            SUM(debit_amount) as total_amount
        FROM banking_transactions
        WHERE account_number = '8314462'
            AND debit_amount > 0
            AND receipt_id IS NULL
        GROUP BY EXTRACT(YEAR FROM transaction_date)
        ORDER BY year
    """)
    
    for year, count, amount in cur.fetchall():
        print(f"  {int(year)}: {count:4d} transactions, ${amount:11,.2f}")
    
    # Analyze transaction patterns
    print("\n" + "=" * 80)
    print("UNMATCHED TRANSACTION PATTERNS")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount
        FROM banking_transactions
        WHERE account_number = '8314462'
            AND debit_amount > 0
            AND receipt_id IS NULL
        ORDER BY transaction_date
    """)
    
    transactions = cur.fetchall()
    
    # Categorize by pattern
    atm_pattern = []
    branch_pattern = []
    fee_pattern = []
    debit_memo_pattern = []
    transfer_pattern = []
    check_pattern = []
    other_pattern = []
    
    for txn_id, date, desc, amount in transactions:
        desc_upper = desc.upper() if desc else ""
        
        if any(keyword in desc_upper for keyword in ['ATM', 'ABM', 'AUTOMATED BANKING MACHINE']):
            atm_pattern.append((txn_id, date, desc, amount))
        elif any(keyword in desc_upper for keyword in ['BRANCH', 'TELLER']):
            branch_pattern.append((txn_id, date, desc, amount))
        elif any(keyword in desc_upper for keyword in ['FEE', 'CHARGE', 'SERVICE CHARGE']):
            fee_pattern.append((txn_id, date, desc, amount))
        elif 'DEBIT MEMO' in desc_upper or 'DB MEMO' in desc_upper:
            debit_memo_pattern.append((txn_id, date, desc, amount))
        elif any(keyword in desc_upper for keyword in ['TRANSFER', 'XFER', 'E-TRANSFER']):
            transfer_pattern.append((txn_id, date, desc, amount))
        elif any(keyword in desc_upper for keyword in ['CHEQUE', 'CHECK', 'CHQ']):
            check_pattern.append((txn_id, date, desc, amount))
        else:
            other_pattern.append((txn_id, date, desc, amount))
    
    # Print pattern summaries
    print("\nPattern Distribution:")
    print(f"  ATM/ABM Withdrawals: {len(atm_pattern):3d} transactions, ${sum(x[3] for x in atm_pattern):11,.2f}")
    print(f"  Branch Withdrawals:  {len(branch_pattern):3d} transactions, ${sum(x[3] for x in branch_pattern):11,.2f}")
    print(f"  Banking Fees:        {len(fee_pattern):3d} transactions, ${sum(x[3] for x in fee_pattern):11,.2f}")
    print(f"  Debit Memos:         {len(debit_memo_pattern):3d} transactions, ${sum(x[3] for x in debit_memo_pattern):11,.2f}")
    print(f"  Transfers:           {len(transfer_pattern):3d} transactions, ${sum(x[3] for x in transfer_pattern):11,.2f}")
    print(f"  Cheques:             {len(check_pattern):3d} transactions, ${sum(x[3] for x in check_pattern):11,.2f}")
    print(f"  Other/Unclassified:  {len(other_pattern):3d} transactions, ${sum(x[3] for x in other_pattern):11,.2f}")
    
    # Show samples of each pattern type
    print("\n" + "=" * 80)
    print("SAMPLE TRANSACTIONS BY PATTERN")
    print("=" * 80)
    
    for pattern_name, pattern_list in [
        ("ATM/ABM Withdrawals", atm_pattern),
        ("Branch Withdrawals", branch_pattern),
        ("Banking Fees", fee_pattern),
        ("Debit Memos", debit_memo_pattern),
        ("Transfers", transfer_pattern),
        ("Cheques", check_pattern),
        ("Other/Unclassified", other_pattern)
    ]:
        if pattern_list:
            print(f"\n{pattern_name} (showing up to 5 samples):")
            for txn_id, date, desc, amount in pattern_list[:5]:
                print(f"  {date} | ${amount:9,.2f} | {desc[:70]}")
            if len(pattern_list) > 5:
                print(f"  ... and {len(pattern_list) - 5} more")
    
    # Summary recommendation
    print("\n" + "=" * 80)
    print("RECOMMENDED ACTIONS")
    print("=" * 80)
    
    actionable_count = len(atm_pattern) + len(branch_pattern) + len(fee_pattern) + len(debit_memo_pattern) + len(transfer_pattern)
    actionable_amount = (sum(x[3] for x in atm_pattern) + 
                        sum(x[3] for x in branch_pattern) + 
                        sum(x[3] for x in fee_pattern) + 
                        sum(x[3] for x in debit_memo_pattern) +
                        sum(x[3] for x in transfer_pattern))
    
    print(f"\n1. Create banking event receipts for {actionable_count} transactions (${actionable_amount:,.2f})")
    print(f"   - This would improve match rate from 88.8% to ~{88.8 + (actionable_count/total_debits*100):.1f}%")
    print(f"\n2. Cheques require check register: {len(check_pattern)} transactions (${sum(x[3] for x in check_pattern):,.2f})")
    print(f"\n3. Other transactions need manual review: {len(other_pattern)} transactions (${sum(x[3] for x in other_pattern):,.2f})")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
