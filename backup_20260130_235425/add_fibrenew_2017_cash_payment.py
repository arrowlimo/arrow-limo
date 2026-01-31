#!/usr/bin/env python3
"""
Add 2017 Fibrenew cash payment to banking_transactions.

Payment Details:
- Date: March 26, 2019
- Amount: $700.00 (Cash)
- Invoices paid: 7598 ($472.50) + 7848 ($227.50)
- Source: L:\\limo\\receipts\\fibrenew_0001.xlsx
"""

import psycopg2
import os
from datetime import date

def get_db_connection():
    """Create database connection."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def add_fibrenew_cash_payment():
    """Add the 2017 Fibrenew cash payment to banking_transactions."""
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Payment details from fibrenew_0001.xlsx
        payment_date = date(2019, 3, 26)
        payment_amount = 700.00
        description = "Cash Payment - FIBRENEW (Invoice 7598 Rent $472.50 + Invoice 7704 Utilities $227.50) - Source: fibrenew_0001.xlsx"
        
        print("ADDING 2017 FIBRENEW CASH PAYMENT")
        print("=" * 80)
        print(f"Date: {payment_date}")
        print(f"Amount: ${payment_amount:,.2f}")
        print(f"Method: Cash")
        print(f"Invoice 7598 (Rent): $472.50")
        print(f"Invoice 7704 (Utilities): $227.50")
        print()
        
        # Check if this payment already exists
        cur.execute("""
            SELECT transaction_id, transaction_date, description
            FROM banking_transactions
            WHERE transaction_date = %s
              AND description ILIKE '%fibrenew%'
              AND description ILIKE '%700%'
        """, (payment_date,))
        
        existing = cur.fetchone()
        
        if existing:
            print(f"✗ Payment already exists:")
            print(f"  ID: {existing[0]}")
            print(f"  Date: {existing[1]}")
            print(f"  Description: {existing[2]}")
            return
        
        # Insert the cash payment
        cur.execute("""
            INSERT INTO banking_transactions 
                (account_number, transaction_date, description, credit_amount, debit_amount, category)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING transaction_id
        """, ('CASH', payment_date, description, payment_amount, 0, 'Rent/Utilities'))
        
        transaction_id = cur.fetchone()[0]
        conn.commit()
        
        print(f"\n✓ Successfully added cash payment:")
        print(f"  Transaction ID: {transaction_id}")
        print(f"  Date: {payment_date}")
        print(f"  Amount: ${payment_amount:,.2f}")
        print(f"  Description: {description}")
        
        # Update rent_debt_ledger
        print(f"\nNow run: python scripts/rebuild_fibrenew_ledger_with_opening.py --write")
        print(f"This will add the payment to the debt ledger.")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    add_fibrenew_cash_payment()
