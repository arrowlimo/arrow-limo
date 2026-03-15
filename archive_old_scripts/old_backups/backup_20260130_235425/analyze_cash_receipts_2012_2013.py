#!/usr/bin/env python
"""
Analyze cash receipts in 2012-2013

Identifies cash transactions (deposits and expenses) from banking data.
"""

import psycopg2
import os

def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def analyze_cash_receipts():
    """Analyze cash transactions in 2012-2013."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("CASH RECEIPTS ANALYSIS: 2012-2013")
    print("=" * 80)
    print()
    
    # Cash deposit patterns
    cash_deposit_patterns = [
        '%CASH DEPOSIT%',
        '%DEPOSIT CASH%',
        '%CASH DEP%',
        '%CSH DEP%',
        '%BRANCH DEPOSIT%',
        '%ATM DEPOSIT%',
        '%ABM DEPOSIT%'
    ]
    
    # Cash withdrawal/expense patterns
    cash_expense_patterns = [
        '%CASH WITHDRAWAL%',
        '%ATM WITHDRAWAL%',
        '%ABM WITHDRAWAL%',
        '%CASH ADVANCE%',
        '%PETTY CASH%'
    ]
    
    for year in [2012, 2013]:
        print(f"\n{'=' * 80}")
        print(f"{year} CASH TRANSACTIONS")
        print(f"{'=' * 80}\n")
        
        # Cash deposits (credits)
        print(f"Cash Deposits (Income):")
        print("-" * 80)
        
        deposit_conditions = ' OR '.join([f"UPPER(description) LIKE '{p}'" for p in cash_deposit_patterns])
        
        query = f"""
            SELECT 
                transaction_date,
                description,
                credit_amount,
                account_number
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = {year}
            AND credit_amount > 0
            AND ({deposit_conditions})
            ORDER BY transaction_date
        """
        
        cur.execute(query)
        
        deposits = cur.fetchall()
        
        if deposits:
            total_deposits = sum(row[2] for row in deposits)
            print(f"Found {len(deposits)} cash deposit transactions totaling ${total_deposits:,.2f}\n")
            
            for txn_date, desc, amount, account in deposits[:20]:  # Show first 20
                print(f"  {txn_date} | ${amount:>10,.2f} | {desc[:50]}")
            
            if len(deposits) > 20:
                print(f"\n  ... and {len(deposits) - 20} more")
        else:
            print("No cash deposits found with standard cash keywords.\n")
        
        print()
        
        # Cash withdrawals/expenses (debits)
        print(f"Cash Withdrawals/Expenses:")
        print("-" * 80)
        
        expense_conditions = ' OR '.join([f"UPPER(description) LIKE '{p}'" for p in cash_expense_patterns])
        
        query = f"""
            SELECT 
                transaction_date,
                description,
                debit_amount,
                account_number
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = {year}
            AND debit_amount > 0
            AND ({expense_conditions})
            ORDER BY transaction_date
        """
        
        cur.execute(query)
        
        expenses = cur.fetchall()
        
        if expenses:
            total_expenses = sum(row[2] for row in expenses)
            print(f"Found {len(expenses)} cash withdrawal transactions totaling ${total_expenses:,.2f}\n")
            
            for txn_date, desc, amount, account in expenses[:20]:  # Show first 20
                print(f"  {txn_date} | ${amount:>10,.2f} | {desc[:50]}")
            
            if len(expenses) > 20:
                print(f"\n  ... and {len(expenses) - 20} more")
        else:
            print("No cash withdrawals found with standard cash keywords.\n")
        
        print()
        
        # Summary for year
        print(f"Summary for {year}:")
        print("-" * 80)
        deposit_count = len(deposits)
        deposit_total = sum(row[2] for row in deposits) if deposits else 0
        expense_count = len(expenses)
        expense_total = sum(row[2] for row in expenses) if expenses else 0
        
        print(f"  Cash deposits: {deposit_count:>4} transactions, ${deposit_total:>12,.2f}")
        print(f"  Cash expenses: {expense_count:>4} transactions, ${expense_total:>12,.2f}")
        print(f"  Net cash flow: {' ' * 18} ${deposit_total - expense_total:>12,.2f}")
        print()
    
    # Check receipts table for cash-related entries
    print(f"\n{'=' * 80}")
    print("RECEIPTS TABLE - CASH ENTRIES (2012-2013)")
    print(f"{'=' * 80}\n")
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) IN (2012, 2013)
        AND (
            UPPER(description) LIKE '%CASH%'
            OR UPPER(vendor_name) LIKE '%CASH%'
            OR UPPER(category) LIKE '%CASH%'
        )
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    receipt_cash = cur.fetchall()
    
    if receipt_cash:
        for year, count, total in receipt_cash:
            print(f"{int(year)}: {count} cash-related receipts totaling ${total:,.2f}")
    else:
        print("No cash-related receipts found in receipts table.")
    
    print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    analyze_cash_receipts()
