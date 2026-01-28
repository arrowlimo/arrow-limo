#!/usr/bin/env python3
"""
Search for FAS GAS PLUS banking transaction
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
    print("SEARCH FOR: FAS GAS PLUS")
    print("=" * 120)
    
    # Search for FAS GAS in banking transactions
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            posted_date,
            description,
            debit_amount,
            credit_amount
        FROM banking_transactions
        WHERE description ILIKE '%FAS%'
        ORDER BY transaction_date DESC
        LIMIT 20
    """)
    
    transactions = cur.fetchall()
    print(f"\nFound {len(transactions)} 'FAS' transactions:\n")
    for txn in transactions:
        bid, bdate, pdate, bdesc, damt, camt = txn
        amt = damt if damt and damt > 0 else camt
        print(f"ID {bid:6} | TxnDate: {bdate} | PostedDate: {pdate} | {bdesc[:60]:60} | ${amt:>10.2f}")
    
    print("\n" + "=" * 120)
    print("SEARCH FOR: All $135 amounts on any date (Sept 2012)")
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
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        AND EXTRACT(MONTH FROM transaction_date) = 9
        ORDER BY transaction_date, posted_date
    """)
    
    transactions = cur.fetchall()
    print(f"\nFound {len(transactions)} $135.00 transactions in Sept 2012:\n")
    for txn in transactions:
        bid, bdate, pdate, bdesc, damt, camt = txn
        amt = damt if damt and damt > 0 else camt
        print(f"ID {bid:6} | TxnDate: {bdate} | PostedDate: {pdate} | {bdesc[:60]:60} | ${amt:>10.2f}")
    
    print("\n" + "=" * 120)
    print("SEARCH FOR: GAS/FUEL transactions in Sept 2012 between $130-$140")
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
        WHERE (description ILIKE '%GAS%' OR description ILIKE '%FUEL%')
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        AND EXTRACT(MONTH FROM transaction_date) = 9
        AND ((debit_amount >= 130 AND debit_amount <= 140) OR (credit_amount >= 130 AND credit_amount <= 140))
        ORDER BY transaction_date
    """)
    
    transactions = cur.fetchall()
    print(f"\nFound {len(transactions)} fuel/gas transactions:\n")
    for txn in transactions:
        bid, bdate, pdate, bdesc, damt, camt = txn
        amt = damt if damt and damt > 0 else camt
        print(f"ID {bid:6} | TxnDate: {bdate} | PostedDate: {pdate} | {bdesc[:60]:60} | ${amt:>10.2f}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
