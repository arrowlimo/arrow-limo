#!/usr/bin/env python3
"""
Find cheques 215 and 216 in March 2012 banking_transactions.
Also check if they exist but with wrong description/reference.
"""

import psycopg2
import os

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
    
    print("=" * 80)
    print("SEARCHING FOR CHEQUES 215 AND 216 IN MARCH 2012")
    print("=" * 80)
    
    # Search for cheque 216 ($100.00 around Mar 19, 2012)
    print("\n1. Looking for cheque 216 ($100.00 on/near Mar 19, 2012):")
    print("-" * 80)
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            balance,
            account_number
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND transaction_date BETWEEN '2012-03-18' AND '2012-03-20'
        AND (debit_amount = 100.00 OR description ILIKE '%216%' OR description ILIKE '%17320440%')
        ORDER BY transaction_date, transaction_id
    """)
    
    results = cur.fetchall()
    if results:
        for row in results:
            print(f"ID: {row[0]}")
            print(f"Date: {row[1]}")
            print(f"Description: {row[2]}")
            print(f"Debit: ${row[3] or 0:.2f}")
            print(f"Credit: ${row[4] or 0:.2f}")
            print(f"Balance: ${row[5] or 0:.2f}")
            print(f"Account: {row[6]}")
            print("-" * 40)
    else:
        print("[FAIL] NO MATCHES FOUND for cheque 216")
    
    # Search for cheque 215 ($150.00 around Mar 19, 2012)
    print("\n2. Looking for cheque 215 ($150.00 on/near Mar 19, 2012):")
    print("-" * 80)
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            balance,
            account_number
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND transaction_date BETWEEN '2012-03-18' AND '2012-03-20'
        AND (debit_amount = 150.00 OR description ILIKE '%215%')
        ORDER BY transaction_date, transaction_id
    """)
    
    results = cur.fetchall()
    if results:
        for row in results:
            print(f"ID: {row[0]}")
            print(f"Date: {row[1]}")
            print(f"Description: {row[2]}")
            print(f"Debit: ${row[3] or 0:.2f}")
            print(f"Credit: ${row[4] or 0:.2f}")
            print(f"Balance: ${row[5] or 0:.2f}")
            print(f"Account: {row[6]}")
            print("-" * 40)
    else:
        print("[FAIL] NO MATCHES FOUND for cheque 215")
    
    # Show ALL Mar 19 transactions
    print("\n3. ALL transactions on Mar 19, 2012:")
    print("-" * 80)
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            balance
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND transaction_date = '2012-03-19'
        ORDER BY transaction_id
    """)
    
    results = cur.fetchall()
    if results:
        for row in results:
            print(f"ID: {row[0]} | Date: {row[1]} | Debit: ${row[3] or 0:.2f} | Credit: ${row[4] or 0:.2f} | Balance: ${row[5] or 0:.2f}")
            print(f"  Description: {row[2]}")
            print()
    else:
        print("[FAIL] NO TRANSACTIONS on Mar 19, 2012")
    
    # Check the balance progression around Mar 19
    print("\n4. Balance progression Mar 18-20:")
    print("-" * 80)
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            balance
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND transaction_date BETWEEN '2012-03-18' AND '2012-03-20'
        ORDER BY transaction_date, transaction_id
    """)
    
    results = cur.fetchall()
    for row in results:
        tx_type = 'W' if row[2] and row[2] > 0 else 'D'
        amount = row[2] if row[2] else row[3]
        print(f"{row[0]} | {tx_type} | ${amount:>9.2f} | Balance: ${row[4]:>10.2f} | {row[1][:60]}")
    
    # From your CIBC statement image, the balances should be:
    print("\n" + "=" * 80)
    print("EXPECTED FROM CIBC STATEMENT (Mar 19):")
    print("=" * 80)
    print("Balance forward: $2,894.74")
    print("After cheque 216 ($100): $2,674.40")
    print("After cheque 215 ($150): $2,524.40")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
