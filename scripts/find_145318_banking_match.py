#!/usr/bin/env python3
"""
Find banking transactions near 09/15-09/17/2012 for fuel purchases.
Show all transactions in this date range and amounts.
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 120)
    print("BANKING TRANSACTIONS: 09/15-09/17/2012 (Fuel-related)")
    print("=" * 120)
    
    # Find banking transactions in this date range
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            posted_date,
            description,
            debit_amount,
            credit_amount,
            account_number,
            reconciliation_status
        FROM banking_transactions
        WHERE transaction_date >= '2012-09-15'
        AND transaction_date <= '2012-09-17'
        AND (description ILIKE '%FAS%' OR description ILIKE '%FUEL%' OR description ILIKE '%SHELL%' OR description ILIKE '%GAS%')
        ORDER BY transaction_date, debit_amount
    """)
    
    transactions = cur.fetchall()
    
    if transactions:
        print(f"\nFound {len(transactions)} fuel-related banking transactions:\n")
        for txn in transactions:
            bid, bdate, pdate, bdesc, damt, camt, acct, status = txn
            amt = damt if damt and damt > 0 else camt
            print(f"Banking ID: {bid}")
            print(f"  Transaction Date: {bdate}")
            print(f"  Posted Date: {pdate}")
            print(f"  Description: {bdesc}")
            print(f"  Amount: ${amt:.2f}")
            print(f"  Account: {acct}")
            print(f"  Recon Status: {status}")
            print()
    else:
        print("\n❌ No fuel transactions found in banking for 09/15-09/17")
        print("\nTrying broader search (all transactions in date range)...\n")
        
        cur.execute("""
            SELECT 
                transaction_id,
                transaction_date,
                posted_date,
                description,
                debit_amount,
                credit_amount,
                account_number
            FROM banking_transactions
            WHERE transaction_date >= '2012-09-15'
            AND transaction_date <= '2012-09-17'
            ORDER BY transaction_date, debit_amount
        """)
        
        transactions = cur.fetchall()
        print(f"All transactions for 09/15-09/17:\n")
        for txn in transactions:
            bid, bdate, pdate, bdesc, damt, camt, acct = txn
            amt = damt if damt and damt > 0 else camt
            print(f"ID {bid:4} | {bdate} | {bdesc[:50]:50} | ${amt:>10.2f}")
    
    # Check if any $135.00 amounts exist
    print("\n" + "=" * 120)
    print("SEARCH FOR $135.00 TRANSACTIONS (any date range)")
    print("=" * 120)
    
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            posted_date,
            description,
            debit_amount,
            credit_amount
        FROM banking_transactions
        WHERE (ABS(debit_amount - 135.00) < 0.01 OR ABS(credit_amount - 135.00) < 0.01)
        ORDER BY transaction_date DESC
        LIMIT 10
    """)
    
    amounts = cur.fetchall()
    if amounts:
        print(f"\nFound {len(amounts)} transactions of ~$135.00:\n")
        for txn in amounts:
            bid, bdate, pdate, bdesc, damt, camt = txn
            amt = damt if damt and damt > 0 else camt
            print(f"Banking {bid}: {bdate} | {pdate} | {bdesc[:60]:60} | ${amt:>10.2f}")
    else:
        print("\nNo $135.00 transactions found in banking")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
