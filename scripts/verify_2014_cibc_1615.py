#!/usr/bin/env python3
"""
Verify 2014 CIBC 1615 account reconciliation with running balance check.
"""

import psycopg2
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def verify_2014_cibc_1615():
    """Verify 2014 CIBC 1615 monthly reconciliation."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get all 2014 transactions for account 1615
        cur.execute("""
            SELECT 
                transaction_date, 
                description, 
                debit_amount, 
                credit_amount, 
                balance
            FROM banking_transactions
            WHERE account_number = '1615'
            AND EXTRACT(YEAR FROM transaction_date) = 2014
            ORDER BY transaction_date, transaction_id
        """)
        
        transactions = cur.fetchall()
        
        print("=" * 100)
        print("2014 CIBC Account 1615 (Business Operating Account) Verification")
        print("=" * 100)
        print()
        
        # Group by month
        from collections import defaultdict
        months = defaultdict(list)
        
        for txn in transactions:
            date, desc, debit, credit, balance = txn
            month_key = date.strftime('%Y-%m')
            months[month_key].append((date, desc, debit, credit, balance))
        
        total_debits = Decimal('0.00')
        total_credits = Decimal('0.00')
        all_valid = True
        
        # Print each month
        for month_key in sorted(months.keys()):
            month_txns = months[month_key]
            month_label = month_key.replace('2014-', '')
            
            # Extract month number
            month_num = int(month_key.split('-')[1])
            month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            month_name = month_names[month_num]
            
            print(f"\n{month_name} 2014:")
            print(f"{'Date':<12} {'Description':<30} {'Debit':<12} {'Credit':<12} {'Balance':<12}")
            print("-" * 82)
            
            month_debits = Decimal('0.00')
            month_credits = Decimal('0.00')
            month_opening = None
            month_closing = None
            
            for date, desc, debit, credit, balance in month_txns:
                if desc == "Opening balance":
                    month_opening = balance
                if desc == "Closing balance":
                    month_closing = balance
                
                debit_str = f"${debit:.2f}" if debit else "-"
                credit_str = f"${credit:.2f}" if credit else "-"
                balance_str = f"${balance:.2f}" if balance else "-"
                
                print(f"{str(date):<12} {desc:<30} {debit_str:>11} {credit_str:>11} {balance_str:>11}")
                
                if debit:
                    month_debits += debit
                    total_debits += debit
                if credit:
                    month_credits += credit
                    total_credits += credit
            
            print(f"{'MONTH TOTAL':<12} {'':<30} ${month_debits:>10.2f} ${month_credits:>10.2f}")
            
            # Verify opening/closing
            if month_opening and month_closing:
                print(f"  Opening: ${month_opening:.2f} | Closing: ${month_closing:.2f} | Change: ${month_closing - month_opening:.2f}")
        
        print()
        print("=" * 100)
        print(f"2014 TOTAL: Debits: ${total_debits:.2f} | Credits: ${total_credits:.2f}")
        print(f"Transactions imported: {len(transactions)}")
        print(f"Final balance: Dec 31: ${transactions[-1][4]:.2f}" if transactions else "No transactions")
        print("=" * 100)
        
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    verify_2014_cibc_1615()
