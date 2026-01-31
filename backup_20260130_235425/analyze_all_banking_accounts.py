#!/usr/bin/env python3
"""
Complete overview of all banking accounts in database.
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("ALL BANKING ACCOUNTS - COMPLETE OVERVIEW")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            account_number,
            COUNT(*) as total_transactions,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date,
            COUNT(CASE WHEN debit_amount > 0 THEN 1 END) as total_debits,
            COUNT(CASE WHEN debit_amount > 0 AND receipt_id IS NOT NULL THEN 1 END) as matched_debits,
            SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as total_debit_amount
        FROM banking_transactions
        GROUP BY account_number
        ORDER BY account_number
    """)
    
    accounts = cur.fetchall()
    
    print(f"\n{'Account':<20} {'Transactions':>12} {'Date Range':^23} {'Debits':>10} {'Matched':>10} {'Match %':>8} {'Total Debits':>15}")
    print("-" * 100)
    
    bank_mapping = {
        '0228362': 'CIBC',
        '1010': 'CIBC',
        '1615': 'CIBC',
        '3648117': 'CIBC',
        '8314462': 'CIBC',
        '903990106011': 'Scotia'
    }
    
    total_transactions = 0
    total_debits = 0
    total_matched = 0
    total_debit_amount = 0
    
    for acct, txns, first_date, last_date, debits, matched, debit_amt in accounts:
        match_pct = 100 * matched / debits if debits > 0 else 0
        bank = bank_mapping.get(acct, 'Unknown')
        display_acct = f"{bank} {acct}"
        
        print(f"{display_acct:<20} {txns:>12,} {first_date} - {last_date} {debits:>10,} {matched:>10,} {match_pct:>7.1f}% ${debit_amt:>13,.2f}")
        
        total_transactions += txns
        total_debits += debits
        total_matched += matched
        total_debit_amount += debit_amt
    
    print("-" * 100)
    overall_match = 100 * total_matched / total_debits if total_debits > 0 else 0
    print(f"{'TOTAL':<20} {total_transactions:>12,} {' '*23} {total_debits:>10,} {total_matched:>10,} {overall_match:>7.1f}% ${total_debit_amount:>13,.2f}")
    
    # Summary by bank
    print("\n" + "=" * 100)
    print("SUMMARY BY BANK")
    print("=" * 100)
    
    for bank in ['CIBC', 'Scotia']:
        cur.execute("""
            SELECT 
                COUNT(*) as total_transactions,
                COUNT(CASE WHEN debit_amount > 0 THEN 1 END) as total_debits,
                COUNT(CASE WHEN debit_amount > 0 AND receipt_id IS NOT NULL THEN 1 END) as matched_debits,
                SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as total_debit_amount
            FROM banking_transactions
            WHERE account_number IN (
                SELECT account_number FROM banking_transactions WHERE 1=1
            )
        """)
        
        # Filter by bank
        if bank == 'CIBC':
            accounts_list = ['0228362', '1010', '1615', '3648117', '8314462']
        else:
            accounts_list = ['903990106011']
        
        cur.execute(f"""
            SELECT 
                COUNT(*) as total_transactions,
                COUNT(CASE WHEN debit_amount > 0 THEN 1 END) as total_debits,
                COUNT(CASE WHEN debit_amount > 0 AND receipt_id IS NOT NULL THEN 1 END) as matched_debits,
                SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as total_debit_amount
            FROM banking_transactions
            WHERE account_number = ANY(%s)
        """, (accounts_list,))
        
        row = cur.fetchone()
        if row and row[1] > 0:
            txns, debits, matched, debit_amt = row
            match_pct = 100 * matched / debits if debits > 0 else 0
            print(f"\n{bank}:")
            print(f"  Total transactions: {txns:,}")
            print(f"  Total debits: {debits:,}")
            print(f"  Matched debits: {matched:,} ({match_pct:.1f}%)")
            print(f"  Unmatched debits: {debits - matched:,} ({100-match_pct:.1f}%)")
            print(f"  Total debit amount: ${debit_amt:,.2f}")
    
    # Improvement recommendations
    print("\n" + "=" * 100)
    print("IMPROVEMENT OPPORTUNITIES")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            account_number,
            COUNT(CASE WHEN debit_amount > 0 AND receipt_id IS NULL THEN 1 END) as unmatched,
            SUM(CASE WHEN debit_amount > 0 AND receipt_id IS NULL THEN debit_amount ELSE 0 END) as unmatched_amount
        FROM banking_transactions
        GROUP BY account_number
        HAVING COUNT(CASE WHEN debit_amount > 0 AND receipt_id IS NULL THEN 1 END) > 0
        ORDER BY COUNT(CASE WHEN debit_amount > 0 AND receipt_id IS NULL THEN 1 END) DESC
    """)
    
    print("\nAccounts with unmatched debits:")
    for acct, unmatched, amount in cur.fetchall():
        bank = bank_mapping.get(acct, 'Unknown')
        print(f"  {bank} {acct}: {unmatched:,} unmatched (${amount:,.2f})")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
