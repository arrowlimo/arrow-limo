#!/usr/bin/env python
"""
Cash Box Reconciliation for 2012-2013

Tracks all cash flow through the "cash box":
1. Cash IN: ATM/ABM withdrawals from bank (cash taken from bank into cash box)
2. Cash OUT: Cash payments to vendors (cash leaving cash box)
3. Cash BACK: Cash deposits to bank (cash from cash box back to bank)
4. Calculate cash box balance at any point in time

Purpose: Reconcile all cash transactions to verify cash box balance.
"""

import psycopg2
import os
from datetime import datetime

def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def cash_box_reconciliation():
    """Reconcile cash box for 2012-2013."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    for year in [2012, 2013]:
        print("=" * 80)
        print(f"CASH BOX RECONCILIATION: {year}")
        print("=" * 80)
        print()
        
        # Step 1: Cash INTO cash box (ATM/ABM withdrawals from bank)
        print(f"Step 1: Cash INTO Cash Box (ATM/ABM Withdrawals)")
        print("-" * 80)
        
        cur.execute(f"""
            SELECT 
                transaction_date,
                description,
                debit_amount
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = {year}
            AND debit_amount > 0
            AND (
                UPPER(description) LIKE '%ATM WITHDRAWAL%'
                OR UPPER(description) LIKE '%ABM WITHDRAWAL%'
                OR UPPER(description) LIKE '%CASH WITHDRAWAL%'
            )
            ORDER BY transaction_date
        """)
        
        cash_in = cur.fetchall()
        total_cash_in = float(sum(row[2] for row in cash_in))
        
        print(f"Found {len(cash_in)} ATM/ABM withdrawals totaling ${total_cash_in:,.2f}")
        print(f"\nFirst 10 transactions:")
        for txn_date, desc, amount in cash_in[:10]:
            print(f"  {txn_date} | ${amount:>10,.2f} | {desc[:50]}")
        if len(cash_in) > 10:
            print(f"  ... and {len(cash_in) - 10} more")
        print()
        
        # Step 2: Cash OUT of cash box (cash payments to vendors)
        print(f"Step 2: Cash OUT of Cash Box (Cash Payments to Vendors)")
        print("-" * 80)
        
        # Check receipts table for cash payments
        cur.execute(f"""
            SELECT 
                receipt_date,
                vendor_name,
                gross_amount,
                description,
                category
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = {year}
            AND (
                UPPER(description) LIKE '%CASH%'
                OR UPPER(vendor_name) LIKE '%CASH%'
                OR UPPER(category) LIKE '%CASH%'
            )
            ORDER BY receipt_date
        """)
        
        cash_out = cur.fetchall()
        total_cash_out = float(sum(row[2] for row in cash_out))
        
        print(f"Found {len(cash_out)} cash payments to vendors totaling ${total_cash_out:,.2f}")
        if len(cash_out) > 0:
            print(f"\nFirst 10 transactions:")
            for receipt_date, vendor, amount, desc, category in cash_out[:10]:
                print(f"  {receipt_date} | ${amount:>10,.2f} | {vendor[:30]} | {category}")
            if len(cash_out) > 10:
                print(f"  ... and {len(cash_out) - 10} more")
        print()
        
        # Step 3: Cash BACK to bank (cash deposits)
        print(f"Step 3: Cash BACK to Bank (Cash Deposits)")
        print("-" * 80)
        
        cur.execute(f"""
            SELECT 
                transaction_date,
                description,
                credit_amount
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = {year}
            AND credit_amount > 0
            AND (
                UPPER(description) LIKE '%CASH DEPOSIT%'
                OR UPPER(description) LIKE '%ABM DEPOSIT%'
                OR UPPER(description) LIKE '%ATM DEPOSIT%'
                OR UPPER(description) LIKE '%BRANCH DEPOSIT%'
            )
            ORDER BY transaction_date
        """)
        
        cash_back = cur.fetchall()
        total_cash_back = float(sum(row[2] for row in cash_back))
        
        print(f"Found {len(cash_back)} cash deposits back to bank totaling ${total_cash_back:,.2f}")
        if len(cash_back) > 0:
            print(f"\nAll transactions:")
            for txn_date, desc, amount in cash_back:
                print(f"  {txn_date} | ${amount:>10,.2f} | {desc[:50]}")
        print()
        
        # Step 4: Calculate cash box balance
        print(f"Step 4: Cash Box Balance Calculation")
        print("-" * 80)
        
        opening_balance = 0.00  # Assume no opening cash balance
        
        print(f"Opening balance (assumed):           ${opening_balance:>12,.2f}")
        print(f"+ Cash IN (ATM/ABM withdrawals):     ${total_cash_in:>12,.2f}")
        print(f"- Cash OUT (vendor payments):        ${total_cash_out:>12,.2f}")
        print(f"- Cash BACK (deposits to bank):      ${total_cash_back:>12,.2f}")
        print("-" * 80)
        
        closing_balance = opening_balance + total_cash_in - total_cash_out - total_cash_back
        
        print(f"Closing balance (calculated):        ${closing_balance:>12,.2f}")
        print()
        
        # Interpretation
        if abs(closing_balance) < 1.00:
            print(f"✓ Cash box is BALANCED (within $1.00 tolerance)")
        elif closing_balance > 0:
            print(f"⚠ Cash box shows SURPLUS of ${closing_balance:,.2f}")
            print(f"  Possible reasons:")
            print(f"  - Cash revenue not yet deposited")
            print(f"  - Unrecorded cash expenses")
            print(f"  - Opening balance was higher than assumed")
        else:
            print(f"⚠ Cash box shows SHORTAGE of ${abs(closing_balance):,.2f}")
            print(f"  Possible reasons:")
            print(f"  - Unrecorded ATM withdrawals")
            print(f"  - Cash expenses paid but not recorded as cash")
            print(f"  - Opening balance was lower than assumed")
        
        print()
        print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    cash_box_reconciliation()
