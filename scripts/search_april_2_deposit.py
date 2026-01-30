#!/usr/bin/env python3
"""
Search specifically for the $43,140 Woodridge Ford refinancing deposit on April 2, 2012.
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

def search_april_2_deposit():
    print("🔍 SEARCHING FOR APRIL 2, 2012 DEPOSITS AND $43,140 AMOUNT")
    print("=" * 60)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Search around April 2nd specifically
        cur.execute("""
            SELECT 
                transaction_id,
                account_number,
                transaction_date,
                description,
                credit_amount,
                debit_amount,
                balance
            FROM banking_transactions 
            WHERE transaction_date BETWEEN '2012-04-01' AND '2012-04-05'
              AND (
                  credit_amount IS NOT NULL 
                  OR ABS(COALESCE(credit_amount, debit_amount, 0) - 43140) < 100
              )
            ORDER BY transaction_date, credit_amount DESC NULLS LAST
        """)
        
        april_early_transactions = cur.fetchall()
        
        print(f"Found {len(april_early_transactions)} transactions April 1-5, 2012:\n")
        
        target_found = False
        april_2_transactions = []
        
        for trans_id, account, date, desc, credit, debit, balance in april_early_transactions:
            amount = credit if credit else debit
            trans_type = "DEPOSIT" if credit else "PAYMENT"
            
            print(f"{date} | {trans_type} | ${amount:,.2f} | Account: {account}")
            print(f"  Description: {desc}")
            print(f"  Transaction ID: {trans_id}")
            
            # Check for the specific $43,140 amount
            if amount and abs(float(amount) - 43140) < 50:
                print("  *** POTENTIAL $43,140 MATCH! ***")
                target_found = True
            
            # Check for April 2nd specifically
            if date.day == 2:
                print("  *** APRIL 2ND TRANSACTION ***")
                april_2_transactions.append((trans_id, account, date, desc, credit, debit))
            
            print()
        
        if not target_found:
            print("🔍 EXPANDING SEARCH FOR $43,140 AMOUNT (any date in 2012):")
            print("=" * 55)
            
            cur.execute("""
                SELECT 
                    transaction_id,
                    account_number,
                    transaction_date,
                    description,
                    credit_amount,
                    debit_amount
                FROM banking_transactions 
                WHERE EXTRACT(YEAR FROM transaction_date) = 2012
                  AND (
                      ABS(COALESCE(credit_amount, 0) - 43140) < 100
                      OR ABS(COALESCE(debit_amount, 0) - 43140) < 100
                  )
                ORDER BY transaction_date
            """)
            
            similar_amounts = cur.fetchall()
            
            if similar_amounts:
                print(f"Found {len(similar_amounts)} transactions within $100 of $43,140:\n")
                
                for trans_id, account, date, desc, credit, debit in similar_amounts:
                    amount = credit if credit else debit
                    trans_type = "DEPOSIT" if credit else "PAYMENT"
                    print(f"{date} | {trans_type} | ${amount:,.2f} | {desc}")
                    
                    if abs(float(amount) - 43140) < 10:
                        print("  *** VERY CLOSE TO $43,140! ***")
                    print()
            else:
                print("No transactions found within $100 of $43,140 in 2012")
        
        # Check for refinancing-related terms
        print("\n🏦 SEARCHING FOR REFINANCING TERMS:")
        print("=" * 35)
        
        cur.execute("""
            SELECT 
                transaction_date,
                description,
                credit_amount,
                debit_amount,
                account_number
            FROM banking_transactions 
            WHERE EXTRACT(YEAR FROM transaction_date) = 2012
              AND (
                  UPPER(description) LIKE '%REFINANC%'
                  OR UPPER(description) LIKE '%REFI%'
                  OR UPPER(description) LIKE '%LOAN%'
                  OR UPPER(description) LIKE '%FINANCING%'
                  OR UPPER(description) LIKE '%WOODRIDGE%'
              )
            ORDER BY transaction_date
        """)
        
        refinancing_terms = cur.fetchall()
        
        if refinancing_terms:
            print(f"Found {len(refinancing_terms)} refinancing-related transactions:")
            for date, desc, credit, debit, account in refinancing_terms:
                amount = credit if credit else debit
                trans_type = "DEPOSIT" if credit else "PAYMENT"
                print(f"  {date} | {trans_type} | ${amount:,.2f} | {desc}")
        else:
            print("No explicit refinancing terms found in descriptions")
        
        # Look more broadly at April 2012 deposits
        print(f"\n💰 ALL DEPOSITS APRIL 1-10, 2012:")
        print("=" * 35)
        
        cur.execute("""
            SELECT 
                transaction_date,
                description,
                credit_amount,
                account_number,
                transaction_id
            FROM banking_transactions 
            WHERE transaction_date BETWEEN '2012-04-01' AND '2012-04-10'
              AND credit_amount IS NOT NULL
              AND credit_amount > 5000
            ORDER BY transaction_date, credit_amount DESC
        """)
        
        april_deposits = cur.fetchall()
        
        print(f"Found {len(april_deposits)} deposits >$5K in early April 2012:")
        for date, desc, credit, account, trans_id in april_deposits:
            print(f"  {date} | ${credit:,.2f} | Account {account} | {desc}")
            
            # Special highlighting
            if date.day == 2:
                print(f"    *** APRIL 2ND DEPOSIT ***")
            if abs(float(credit) - 43140) < 1000:
                print(f"    *** CLOSE TO YOUR $43,140 AMOUNT ***")
            if abs(float(credit) - 44186.42) < 1:
                print(f"    *** This is the $44,186.42 we found earlier ***")
        
        # Summary analysis
        print(f"\n📊 VEHICLE FINANCING TIMELINE RECONSTRUCTION:")
        print("=" * 45)
        
        print("Based on the data found:")
        print()
        
        # Check if we found the April 3rd deposit
        april_3_found = False
        for date, desc, credit, account, trans_id in april_deposits:
            if date.day == 3 and credit and abs(float(credit) - 44186.42) < 1:
                april_3_found = True
                print(f"April 3, 2012: ${credit:,.2f} DEPOSIT (\"{desc}\")")
                print(f"  → Likely the Woodridge Ford refinancing deposit")
                print(f"  → Close to your $43,140 figure (difference: ${abs(float(credit) - 43140):,.2f})")
                print(f"  → One day BEFORE vehicle purchases began")
                break
        
        if not april_3_found:
            print("April 2-3, 2012: [Searching for your $43,140 refinancing deposit...]")
        
        print()
        print("April 4, 2012: $40,876.66 PAYMENT (Ford E350 VIN ...32525)")
        print("April 5, 2012: $40,850.57 PAYMENT (Second vehicle)")  
        print("April 9, 2012: $40,511.25 PAYMENT (Third vehicle)")
        print()
        
        print("📋 CONCLUSION:")
        if april_3_found:
            print("The $44,186.42 deposit on April 3rd appears to be the")
            print("Woodridge Ford refinancing you mentioned, providing funds")
            print("for the subsequent vehicle purchases.")
        else:
            print("The $43,140 Woodridge Ford refinancing deposit may be:")
            print("• In a different account not yet analyzed")
            print("• Described with different terminology")
            print("• Split across multiple transactions")
            print("• The $44,186.42 deposit with slight amount difference")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {str(e)}")
        raise
        
    finally:
        cur.close()
        conn.close()

def main():
    search_april_2_deposit()

if __name__ == "__main__":
    main()