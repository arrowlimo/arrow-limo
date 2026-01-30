#!/usr/bin/env python3
"""
Verify banking reconciliation with hardcoded opening balances and year-end totals.
Compare to running balance calculations for perfect matching.
"""

import psycopg2
from datetime import datetime
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

# Known opening balances from manual verification
KNOWN_OPENING_BALANCES = {
    ('0228362', 2012): 7177.34,   # January 1, 2012 CIBC
    ('0228362', 2013): None,       # Need to verify
    ('0228362', 2014): None,       # Need to verify
    ('903990106011', 2012): None,  # Scotia - need first transaction date
}

# Known year-end closing balances from statements
KNOWN_CLOSING_BALANCES = {
    ('0228362', 2012): 5643.63,    # July 31, 2012 CIBC (last verified month)
    ('0228362', 2013): None,       # Need to verify
    ('903990106011', 2012): None,  # Scotia - need verification
}

# Hardcoded statement metrics for fast verification (counts/totals/open/close)
HARDCODED_YEAR_METRICS = {
    ('0228362', 2012): {
        'opening_statement_date': '2012-01-01',
        'opening_statement_balance': 7177.34,
        'closing_statement_date': '2012-12-31',
        'closing_statement_balance': 21.21,
    },
    ('903990106011', 2012): {
        'opening_statement_date': '2011-12-30',
        'opening_statement_balance': 40.00,
        'closing_statement_date': '2012-12-31',
        'closing_statement_balance': 952.04,
        'total_debits': 51004.12,
        'debit_count': 50,
        'total_credits': 51950.93,
        'credit_count': 22,
    },
}

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("BANKING RECONCILIATION VERIFICATION")
    print("=" * 80)
    
    # STEP 1: Get all banking data grouped by account and year
    print("\nSTEP 1: Loading banking data by account and year...")
    
    cur.execute("""
        SELECT 
            account_number,
            EXTRACT(YEAR FROM transaction_date) as year,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date,
            COUNT(*) as txn_count,
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits
        FROM banking_transactions
        WHERE account_number IN ('0228362', '903990106011')
        GROUP BY account_number, EXTRACT(YEAR FROM transaction_date)
        ORDER BY account_number, year
    """)
    
    account_years = cur.fetchall()
    
    print(f"\nFound {len(account_years)} account-year combinations")
    print("\nAccount-Year Summary:")
    for row in account_years:
        acct, year, first, last, count, debits, credits = row
        acct_name = "CIBC" if acct == '0228362' else "Scotia"
        print(f"  {acct_name} {int(year)}: {first} to {last} | "
              f"{count:,} txns | Debits: ${float(debits):,.2f} | Credits: ${float(credits):,.2f}")
    
    # STEP 2: Calculate running balances and verify against known values
    print("\n" + "=" * 80)
    print("STEP 2: CALCULATING RUNNING BALANCES")
    print("=" * 80)
    
    for acct_num in ['0228362', '903990106011']:
        acct_name = "CIBC" if acct_num == '0228362' else "Scotia"
        
        print(f"\n{'=' * 80}")
        print(f"ACCOUNT: {acct_name} ({acct_num})")
        print('=' * 80)
        
        # Get all transactions for this account in chronological order
        cur.execute("""
            SELECT 
                transaction_id,
                transaction_date,
                description,
                debit_amount,
                credit_amount,
                balance
            FROM banking_transactions
            WHERE account_number = %s
            ORDER BY transaction_date, transaction_id
        """, (acct_num,))
        
        transactions = cur.fetchall()
        
        if not transactions:
            print(f"  No transactions found")
            continue
        
        print(f"\nTotal transactions: {len(transactions):,}")
        
        # Group by year for verification
        years = defaultdict(list)
        for txn in transactions:
            year = txn[1].year
            years[year].append(txn)
        
        # Verify each year
        for year in sorted(years.keys()):
            year_txns = years[year]
            print(f"\n{'-' * 80}")
            print(f"YEAR {year} - {len(year_txns):,} transactions")
            print('-' * 80)
            
            # Check for known opening balance
            opening_balance_key = (acct_num, year)
            known_opening = KNOWN_OPENING_BALANCES.get(opening_balance_key)
            
            if known_opening is not None:
                print(f"\n  Known opening balance: ${known_opening:,.2f}")
            else:
                print(f"\n  ⚠️  No known opening balance for {year}")
            
            # Calculate running balance
            first_txn = year_txns[0]
            last_txn = year_txns[-1]
            
            txn_id, txn_date, desc, debit, credit, db_balance = first_txn
            
            # If we have a known opening balance, use it
            if known_opening is not None:
                calculated_balance = known_opening
                print(f"  Starting from known opening: ${calculated_balance:,.2f}")
            elif db_balance is not None:
                # Use first transaction's balance as reference
                # Work backwards: balance + debit - credit = opening
                calculated_balance = float(db_balance) + float(debit or 0) - float(credit or 0)
                print(f"  Calculated opening (from first txn): ${calculated_balance:,.2f}")
            else:
                print(f"  ⚠️  Cannot determine opening balance")
                calculated_balance = 0
            
            # Verify first transaction
            first_expected = calculated_balance - float(first_txn[3] or 0) + float(first_txn[4] or 0)
            first_db_balance = first_txn[5]
            
            print(f"\n  First transaction: {first_txn[1]}")
            print(f"    Opening: ${calculated_balance:,.2f}")
            print(f"    Debit: ${float(first_txn[3] or 0):,.2f} | Credit: ${float(first_txn[4] or 0):,.2f}")
            print(f"    Expected balance: ${first_expected:,.2f}")
            print(f"    Database balance: ${float(first_db_balance or 0):,.2f}")
            
            if first_db_balance and abs(first_expected - float(first_db_balance)) < 0.01:
                print(f"    ✅ MATCH (difference: ${abs(first_expected - float(first_db_balance)):.2f})")
            elif first_db_balance:
                print(f"    ❌ MISMATCH (difference: ${abs(first_expected - float(first_db_balance)):.2f})")
            
            # Calculate through all transactions
            running_balance = calculated_balance
            mismatches = 0
            
            for i, txn in enumerate(year_txns):
                txn_id, txn_date, desc, debit, credit, db_balance = txn
                
                # Apply transaction
                running_balance = running_balance - float(debit or 0) + float(credit or 0)
                
                # Compare to database balance if available
                if db_balance is not None:
                    diff = abs(running_balance - float(db_balance))
                    if diff > 0.01:
                        mismatches += 1
            
            # Last transaction verification
            last_expected = running_balance
            last_db_balance = last_txn[5]
            
            print(f"\n  Last transaction: {last_txn[1]}")
            print(f"    Calculated balance: ${last_expected:,.2f}")
            print(f"    Database balance: ${float(last_db_balance or 0):,.2f}")
            
            if last_db_balance and abs(last_expected - float(last_db_balance)) < 0.01:
                print(f"    ✅ MATCH (difference: ${abs(last_expected - float(last_db_balance)):.2f})")
            else:
                print(f"    ❌ MISMATCH (difference: ${abs(last_expected - float(last_db_balance or 0)):.2f})")
            
            # Check against known closing balance
            closing_balance_key = (acct_num, year)
            known_closing = KNOWN_CLOSING_BALANCES.get(closing_balance_key)
            
            if known_closing is not None:
                print(f"\n  Known closing balance: ${known_closing:,.2f}")
                if abs(last_expected - known_closing) < 0.01:
                    print(f"  ✅ CALCULATED MATCHES KNOWN CLOSING")
                else:
                    print(f"  ❌ MISMATCH: Calculated ${last_expected:,.2f} vs Known ${known_closing:,.2f}")
                    print(f"     Difference: ${abs(last_expected - known_closing):.2f}")
            
            # Summary for year
            total_debits = sum(float(txn[3] or 0) for txn in year_txns)
            total_credits = sum(float(txn[4] or 0) for txn in year_txns)
            net_change = total_credits - total_debits
            
            print(f"\n  Year {year} Summary:")
            print(f"    Total debits:  ${total_debits:,.2f}")
            print(f"    Total credits: ${total_credits:,.2f}")
            print(f"    Net change:    ${net_change:,.2f}")
            print(f"    Opening:       ${calculated_balance:,.2f}")
            print(f"    Closing:       ${last_expected:,.2f}")
            print(f"    Mismatches:    {mismatches:,}")

            # Hardcoded statement metrics if available
            metrics_key = (acct_num, year)
            if metrics_key in HARDCODED_YEAR_METRICS:
                m = HARDCODED_YEAR_METRICS[metrics_key]
                print("    Statement (hardcoded):")
                print(f"      Opening {m['opening_statement_date']}: ${m['opening_statement_balance']:,.2f}")
                print(f"      Closing {m['closing_statement_date']}: ${m['closing_statement_balance']:,.2f}")
                print(f"      Debits: ${m['total_debits']:,.2f} ({m['debit_count']} txns)")
                print(f"      Credits: ${m['total_credits']:,.2f} ({m['credit_count']} txns)")
            
            if mismatches == 0:
                print(f"    ✅ PERFECT RECONCILIATION")
            else:
                print(f"    ⚠️  {mismatches:,} transaction mismatches")
    
    # STEP 3: Cross-year verification
    print("\n" + "=" * 80)
    print("STEP 3: CROSS-YEAR VERIFICATION")
    print("=" * 80)
    
    for acct_num in ['0228362', '903990106011']:
        acct_name = "CIBC" if acct_num == '0228362' else "Scotia"
        
        print(f"\n{acct_name} ({acct_num}):")
        
        # Get year-end balances using DISTINCT ON to avoid grouping errors
        cur.execute("""
            SELECT DISTINCT ON (yr) 
                yr as year,
                transaction_date as last_date,
                balance as closing_balance
            FROM (
                SELECT 
                    EXTRACT(YEAR FROM transaction_date) AS yr,
                    transaction_date,
                    transaction_id,
                    balance
                FROM banking_transactions
                WHERE account_number = %s
            ) t
            ORDER BY yr, transaction_date DESC, transaction_id DESC
        """, (acct_num,))
        
        year_ends = cur.fetchall()
        
        for i in range(len(year_ends) - 1):
            curr_year, curr_date, curr_close = year_ends[i]
            next_year, next_date, next_close = year_ends[i + 1]
            
            # Get first transaction of next year
            cur.execute("""
                SELECT transaction_date, balance
                FROM banking_transactions
                WHERE account_number = %s
                AND EXTRACT(YEAR FROM transaction_date) = %s
                ORDER BY transaction_date, transaction_id
                LIMIT 1
            """, (acct_num, next_year))
            
            next_first = cur.fetchone()
            
            if curr_close and next_first and next_first[1]:
                # Calculate what next year opening should be
                # First txn balance + debit - credit = opening
                print(f"  {int(curr_year)} closing: ${float(curr_close):,.2f}")
                print(f"  {int(next_year)} first txn balance: ${float(next_first[1]):,.2f}")
                
                # Note: Can't perfectly verify without seeing first transaction details
                print(f"  ⚠️  Manual verification needed for year boundary")
    
    # STEP 4: Receipt reconciliation impact
    print("\n" + "=" * 80)
    print("STEP 4: RECEIPT RECONCILIATION IMPACT")
    print("=" * 80)
    
    # Check receipts after deduplication
    cur.execute("""
        SELECT 
            COUNT(*) as total_receipts,
            COUNT(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 END) as with_banking,
            SUM(gross_amount) as total_amount
        FROM receipts
        WHERE created_from_banking = TRUE
    """)
    
    receipt_stats = cur.fetchone()
    total_receipts, with_banking, total_amount = receipt_stats
    
    print(f"\nReceipt Statistics (post-deduplication):")
    print(f"  Total receipts: {total_receipts:,}")
    print(f"  Linked to banking: {with_banking:,} ({with_banking/total_receipts*100:.1f}%)")
    print(f"  Total amount: ${float(total_amount):,.2f}")
    
    # Compare to banking debits
    cur.execute("""
        SELECT 
            COUNT(*) as total_debits,
            SUM(debit_amount) as total_debit_amount
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND debit_amount > 0
    """)
    
    banking_stats = cur.fetchone()
    total_debits, total_debit_amount = banking_stats
    
    print(f"\nBanking Statistics (CIBC debits):")
    print(f"  Total debit transactions: {total_debits:,}")
    print(f"  Total debit amount: ${float(total_debit_amount):,.2f}")
    
    # Match rate
    match_rate = with_banking / total_debits * 100
    print(f"\nMatch rate: {match_rate:.1f}% of banking debits have receipts")
    
    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETE")
    print("=" * 80)
    
    conn.close()

if __name__ == "__main__":
    main()
