#!/usr/bin/env python3
"""
Analyze Scotia Bank 2013 transactions and match rates.
"""

import psycopg2

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
    print("SCOTIA BANK 2013 - TRANSACTION ANALYSIS")
    print("=" * 80)
    
    # Get 2013 overview
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
        WHERE account_number = '3677542'
            AND EXTRACT(YEAR FROM transaction_date) = 2013
    """)
    
    row = cur.fetchone()
    total_txns, total_debits, unmatched_debits, total_debit_amt, unmatched_debit_amt, earliest, latest = row
    
    match_rate = 100 * (total_debits - unmatched_debits) / total_debits if total_debits > 0 else 0
    
    print(f"\nScotia Account 3677542 - Year 2013:")
    print(f"  Total transactions: {total_txns:,}")
    print(f"  Total debits: {total_debits:,}")
    print(f"  Matched debits: {total_debits - unmatched_debits:,} ({match_rate:.1f}%)")
    print(f"  Unmatched debits: {unmatched_debits:,} ({100-match_rate:.1f}%)")
    print(f"  Total debit amount: ${total_debit_amt:,.2f}")
    print(f"  Unmatched debit amount: ${unmatched_debit_amt:,.2f}")
    print(f"  Date range: {earliest} to {latest}")
    
    # Get unmatched by month
    print("\n" + "=" * 80)
    print("UNMATCHED DEBITS BY MONTH")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            EXTRACT(MONTH FROM transaction_date) as month,
            COUNT(*) as count,
            SUM(debit_amount) as total_amount
        FROM banking_transactions
        WHERE account_number = '3677542'
            AND EXTRACT(YEAR FROM transaction_date) = 2013
            AND debit_amount > 0
            AND receipt_id IS NULL
        GROUP BY EXTRACT(MONTH FROM transaction_date)
        ORDER BY month
    """)
    
    months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    for month, count, amount in cur.fetchall():
        print(f"  {months[int(month)]}: {count:4d} transactions, ${amount:11,.2f}")
    
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
        WHERE account_number = '3677542'
            AND EXTRACT(YEAR FROM transaction_date) = 2013
            AND debit_amount > 0
            AND receipt_id IS NULL
        ORDER BY transaction_date
    """)
    
    transactions = cur.fetchall()
    
    # Categorize by pattern
    atm_pattern = []
    pos_pattern = []
    preauth_pattern = []
    fee_pattern = []
    nsfnsf_pattern = []
    transfer_pattern = []
    withdrawal_pattern = []
    check_pattern = []
    other_pattern = []
    
    for txn_id, date, desc, amount in transactions:
        desc_upper = desc.upper() if desc else ""
        
        if any(keyword in desc_upper for keyword in ['ATM', 'ABM']):
            atm_pattern.append((txn_id, date, desc, amount))
        elif 'POS' in desc_upper or 'PURCHASE' in desc_upper:
            pos_pattern.append((txn_id, date, desc, amount))
        elif 'PRE-AUTH' in desc_upper or 'PREAUTH' in desc_upper:
            preauth_pattern.append((txn_id, date, desc, amount))
        elif any(keyword in desc_upper for keyword in ['FEE', 'CHARGE', 'SERVICE']):
            fee_pattern.append((txn_id, date, desc, amount))
        elif 'NSF' in desc_upper:
            nsfnsf_pattern.append((txn_id, date, desc, amount))
        elif any(keyword in desc_upper for keyword in ['TRANSFER', 'XFER']):
            transfer_pattern.append((txn_id, date, desc, amount))
        elif 'WITHDRAWAL' in desc_upper or 'WD' in desc_upper:
            withdrawal_pattern.append((txn_id, date, desc, amount))
        elif any(keyword in desc_upper for keyword in ['CHEQUE', 'CHECK', 'CHQ']):
            check_pattern.append((txn_id, date, desc, amount))
        else:
            other_pattern.append((txn_id, date, desc, amount))
    
    # Print pattern summaries
    print("\nPattern Distribution:")
    print(f"  ATM Withdrawals:     {len(atm_pattern):4d} transactions, ${sum(x[3] for x in atm_pattern):11,.2f}")
    print(f"  POS Purchases:       {len(pos_pattern):4d} transactions, ${sum(x[3] for x in pos_pattern):11,.2f}")
    print(f"  Pre-Auth Holds:      {len(preauth_pattern):4d} transactions, ${sum(x[3] for x in preauth_pattern):11,.2f}")
    print(f"  Banking Fees:        {len(fee_pattern):4d} transactions, ${sum(x[3] for x in fee_pattern):11,.2f}")
    print(f"  NSF/Reversals:       {len(nsfnsf_pattern):4d} transactions, ${sum(x[3] for x in nsfnsf_pattern):11,.2f}")
    print(f"  Transfers:           {len(transfer_pattern):4d} transactions, ${sum(x[3] for x in transfer_pattern):11,.2f}")
    print(f"  Withdrawals:         {len(withdrawal_pattern):4d} transactions, ${sum(x[3] for x in withdrawal_pattern):11,.2f}")
    print(f"  Cheques:             {len(check_pattern):4d} transactions, ${sum(x[3] for x in check_pattern):11,.2f}")
    print(f"  Other/Unclassified:  {len(other_pattern):4d} transactions, ${sum(x[3] for x in other_pattern):11,.2f}")
    
    # Show samples
    print("\n" + "=" * 80)
    print("SAMPLE TRANSACTIONS BY PATTERN")
    print("=" * 80)
    
    for pattern_name, pattern_list in [
        ("ATM Withdrawals", atm_pattern),
        ("POS Purchases", pos_pattern),
        ("Pre-Auth Holds", preauth_pattern),
        ("Banking Fees", fee_pattern),
        ("NSF/Reversals", nsfnsf_pattern),
        ("Transfers", transfer_pattern),
        ("Withdrawals", withdrawal_pattern),
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
    
    actionable_count = (len(atm_pattern) + len(pos_pattern) + len(preauth_pattern) + 
                       len(fee_pattern) + len(nsfnsf_pattern) + len(transfer_pattern) + 
                       len(withdrawal_pattern))
    actionable_amount = (sum(x[3] for x in atm_pattern) + 
                        sum(x[3] for x in pos_pattern) + 
                        sum(x[3] for x in preauth_pattern) +
                        sum(x[3] for x in fee_pattern) + 
                        sum(x[3] for x in nsfnsf_pattern) +
                        sum(x[3] for x in transfer_pattern) +
                        sum(x[3] for x in withdrawal_pattern))
    
    print(f"\n1. Create banking event receipts for {actionable_count} transactions (${actionable_amount:,.2f})")
    potential_rate = match_rate + (actionable_count/total_debits*100)
    print(f"   - This would improve match rate from {match_rate:.1f}% to ~{potential_rate:.1f}%")
    print(f"\n2. Cheques require check register: {len(check_pattern)} transactions (${sum(x[3] for x in check_pattern):,.2f})")
    print(f"\n3. Other transactions need manual review: {len(other_pattern)} transactions (${sum(x[3] for x in other_pattern):,.2f})")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
