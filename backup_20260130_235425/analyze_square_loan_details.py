#!/usr/bin/env python3
"""
Detailed Square Capital Loan Payment Analysis

Analyzes all Square Capital loan transactions to understand:
1. Loan deposits (money received)
2. Loan payments/repayments (money paid back)
3. Payment history and balance tracking
"""

import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

def main():
    print('=' * 100)
    print('DETAILED SQUARE CAPITAL LOAN ANALYSIS')
    print('=' * 100)
    
    conn = get_db_conn()
    cur = conn.cursor()
    
    # Get ALL Square Capital related transactions
    print('\nFetching all Square Capital transactions from banking_transactions...')
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            account_number,
            description,
            debit_amount,
            credit_amount,
            balance
        FROM banking_transactions
        WHERE (description ILIKE '%SQ CAP%' 
           OR description ILIKE '%SQUARE CAP%'
           OR description ILIKE '%SQ SQ CAP%'
           OR (description ILIKE '%SQUARE%' AND description ILIKE '%PREAUTHORIZED%'))
        ORDER BY transaction_date
    """)
    
    transactions = cur.fetchall()
    print(f'  Found {len(transactions)} transactions')
    
    print('\n' + '=' * 100)
    print('ALL SQUARE CAPITAL TRANSACTIONS')
    print('=' * 100)
    
    # Separate loans and payments
    loan_deposits = []
    loan_payments = []
    
    for txn in transactions:
        txn_id, date, account, desc, debit, credit, balance = txn
        
        if credit and credit > 0:
            # Money received = Loan deposit
            loan_deposits.append(txn)
            print(f'\n💰 LOAN DEPOSIT #{len(loan_deposits)}:')
            print(f'   Date: {date}')
            print(f'   Amount: ${credit:,.2f}')
            print(f'   Account: {account}')
            print(f'   Description: {desc}')
            
            # Extract loan ID from description
            if 'CAP1622' in desc or 'CAP16' in desc:
                print(f'   → LOAN #1: CAP1622')
            elif 'CAP9152' in desc or 'CAP91' in desc:
                print(f'   → LOAN #2: CAP9152')
        
        if debit and debit > 0:
            # Money paid = Loan payment/repayment
            loan_payments.append(txn)
    
    print(f'\n\n' + '=' * 100)
    print(f'LOAN REPAYMENTS (ALL {len(loan_payments)} PAYMENTS)')
    print('=' * 100)
    
    total_payments = 0
    payments_by_year = {}
    
    for txn in loan_payments:
        txn_id, date, account, desc, debit, credit, balance = txn
        total_payments += debit
        
        year = date.year
        if year not in payments_by_year:
            payments_by_year[year] = []
        payments_by_year[year].append((date, debit, desc))
    
    for year in sorted(payments_by_year.keys()):
        year_payments = payments_by_year[year]
        year_total = sum(p[1] for p in year_payments)
        print(f'\n{year}: {len(year_payments)} payments, Total: ${year_total:,.2f}')
        print('-' * 80)
        for date, amount, desc in year_payments:
            print(f'  {date} | ${amount:>10,.2f} | {desc[:60]}')
    
    print(f'\n' + '=' * 100)
    print('SUMMARY')
    print('=' * 100)
    
    total_loans = sum(t[5] for t in loan_deposits if t[5])
    
    print(f'\nLOAN DEPOSITS:')
    for i, txn in enumerate(loan_deposits, 1):
        date, amount, desc = txn[1], txn[5], txn[3]
        loan_id = 'CAP1622' if 'CAP16' in desc else ('CAP9152' if 'CAP91' in desc else 'UNKNOWN')
        print(f'  Loan #{i} ({loan_id}): ${amount:,.2f} on {date}')
    
    print(f'\n  TOTAL LOANS RECEIVED: ${total_loans:,.2f}')
    print(f'\nLOAN REPAYMENTS:')
    print(f'  Total Payments Made: ${total_payments:,.2f}')
    print(f'  Number of Payments: {len(loan_payments)}')
    
    print(f'\nNET POSITION:')
    net = total_loans - total_payments
    print(f'  Outstanding Balance: ${net:,.2f}')
    
    # Try to identify which payments belong to which loan
    print('\n' + '=' * 100)
    print('PAYMENT ATTRIBUTION ANALYSIS')
    print('=' * 100)
    
    if len(loan_deposits) >= 2:
        loan1_date = loan_deposits[0][1]
        loan1_amount = loan_deposits[0][5]
        loan2_date = loan_deposits[1][1] if len(loan_deposits) > 1 else None
        loan2_amount = loan_deposits[1][5] if len(loan_deposits) > 1 else 0
        
        print(f'\nLoan #1: ${loan1_amount:,.2f} received on {loan1_date}')
        if loan2_date:
            print(f'Loan #2: ${loan2_amount:,.2f} received on {loan2_date}')
        
        # Payments before loan 2
        payments_before_loan2 = [p for p in loan_payments if loan2_date is None or p[1] < loan2_date]
        payments_after_loan2 = [p for p in loan_payments if loan2_date and p[1] >= loan2_date]
        
        total_before = sum(p[4] for p in payments_before_loan2)
        total_after = sum(p[4] for p in payments_after_loan2)
        
        print(f'\nPayments BEFORE Loan #2 ({loan2_date if loan2_date else "N/A"}):')
        print(f'  Count: {len(payments_before_loan2)}')
        print(f'  Total: ${total_before:,.2f}')
        
        if loan2_date:
            print(f'\nPayments AFTER Loan #2 ({loan2_date}):')
            print(f'  Count: {len(payments_after_loan2)}')
            print(f'  Total: ${total_after:,.2f}')
        
        print(f'\nLoan #1 Balance:')
        print(f'  Received: ${loan1_amount:,.2f}')
        print(f'  Paid before Loan #2: ${total_before:,.2f}')
        print(f'  Remaining when Loan #2 taken: ${loan1_amount - total_before:,.2f}')
        
        if loan2_date:
            print(f'\nCombined Balance after Loan #2:')
            print(f'  Loan #1 remaining: ${loan1_amount - total_before:,.2f}')
            print(f'  Loan #2 received: ${loan2_amount:,.2f}')
            print(f'  Total owed: ${(loan1_amount - total_before) + loan2_amount:,.2f}')
            print(f'  Payments after Loan #2: ${total_after:,.2f}')
            print(f'  Current balance: ${(loan1_amount - total_before) + loan2_amount - total_after:,.2f}')
    
    # Check for any Square transactions that might be embedded loan payments
    print('\n' + '=' * 100)
    print('CHECKING FOR EMBEDDED LOAN PAYMENTS IN SQUARE PAYOUTS')
    print('=' * 100)
    
    cur.execute("""
        SELECT COUNT(*), MIN(arrival_date), MAX(arrival_date)
        FROM square_payouts
    """)
    payout_info = cur.fetchone()
    
    if payout_info and payout_info[0] > 0:
        print(f'\nSquare Payouts in database: {payout_info[0]}')
        print(f'  Date range: {payout_info[1]} to {payout_info[2]}')
        print('\n⚠ NOTE: Square Capital payments may be automatically deducted from daily payouts.')
        print('  This means the actual repayment amount could be MUCH higher than visible')
        print('  bank transactions if Square deducts payments before depositing to your bank.')
        print('\n  To get accurate loan payment totals:')
        print('  1. Log into Square Dashboard: https://squareup.com/dashboard')
        print('  2. Go to Capital → Loans')
        print('  3. Check payment history for each loan')
        print('  4. Square shows TOTAL payments including payout deductions')
    else:
        print('\nNo Square payout data available for cross-reference')
    
    cur.close()
    conn.close()
    
    print('\n' + '=' * 100)
    print('✓ ANALYSIS COMPLETE')
    print('=' * 100)

if __name__ == '__main__':
    main()
