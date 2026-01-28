#!/usr/bin/env python3
"""
Square Capital Loan Reconciliation Analysis
Identifies all Square Capital loans and payments across banking and Square data.
"""

import psycopg2
import os
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

def main():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    
    cursor = conn.cursor()
    
    print("SQUARE CAPITAL LOAN RECONCILIATION ANALYSIS")
    print("="*80)
    
    # 1. Square Capital Loan Deposits (Money Received)
    cursor.execute("""
    SELECT 
        transaction_date,
        account_number,
        description,
        credit_amount
    FROM banking_transactions 
    WHERE (description ILIKE '%SQ CAP%' 
       OR description ILIKE '%SQ SQ CAP%'
       OR description ILIKE '%SQUARE CAP%')
      AND credit_amount > 0
    ORDER BY transaction_date
    """)
    
    loan_deposits = cursor.fetchall()
    
    print("\n📈 SQUARE CAPITAL LOANS RECEIVED:")
    print("-" * 60)
    total_loans = 0
    for date, account, desc, amount in loan_deposits:
        total_loans += amount
        print(f"{date} | {account} | ${amount:,.2f}")
        print(f"     {desc}")
        
        # Extract loan ID from description
        if "CAP1622" in desc:
            print(f"     → LOAN #1: SQ CAP1622")
        elif "CAP9152" in desc:
            print(f"     → LOAN #2: SQ CAP9152")
        print()
    
    print(f"💰 TOTAL SQUARE CAPITAL LOANS: ${total_loans:,.2f}")
    
    # 2. Square Capital Loan Payments/Repayments (Money Paid Back)
    cursor.execute("""
    SELECT 
        transaction_date,
        account_number,
        description,
        debit_amount
    FROM banking_transactions 
    WHERE description ILIKE '%SQUARE%'
      AND debit_amount > 0
      AND (description ILIKE '%PREAUTHORIZED DEBIT%'
       OR description ILIKE '%SQUARE, INC%')
    ORDER BY transaction_date
    """)
    
    loan_payments = cursor.fetchall()
    
    print(f"\n💳 SQUARE CAPITAL LOAN PAYMENTS:")
    print("-" * 60)
    total_payments = 0
    payments_by_year = {}
    
    for date, account, desc, amount in loan_payments:
        total_payments += amount
        year = date.year
        if year not in payments_by_year:
            payments_by_year[year] = 0
        payments_by_year[year] += amount
        
        print(f"{date} | {account} | ${amount:,.2f} | {desc}")
    
    print(f"\n💸 TOTAL LOAN PAYMENTS: ${total_payments:,.2f}")
    
    print(f"\nPayments by Year:")
    for year in sorted(payments_by_year.keys()):
        print(f"  {year}: ${payments_by_year[year]:,.2f}")
    
    # 3. Check Square processing activity for embedded loan repayments
    cursor.execute("""
    SELECT 
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        COUNT(*) as total_payments,
        SUM(gross_amount) as total_gross,
        SUM(net_amount) as total_net,
        SUM(total_fees) as total_fees
    FROM payments 
    WHERE payment_method = 'SQUARE'
      AND transaction_date >= '2025-01-08'  -- After first 2025 loan
      AND gross_amount IS NOT NULL
    """)
    
    square_activity = cursor.fetchone()
    
    if square_activity and square_activity[0]:
        first_date, last_date, count, gross, net, fees = square_activity
        avg_fee_rate = (fees / gross * 100) if gross > 0 else 0
        
        print(f"\n📊 SQUARE PROCESSING ACTIVITY (Since Loan #1: Jan 8, 2025):")
        print("-" * 60)
        print(f"Period: {first_date} to {last_date}")
        print(f"Total Transactions: {count:,}")
        print(f"Gross Revenue: ${gross:,.2f}")
        print(f"Net Deposited: ${net:,.2f}")
        print(f"Total Fees: ${fees:,.2f}")
        print(f"Average Fee Rate: {avg_fee_rate:.2f}%")
        
        # Estimate normal fees vs potential loan repayments
        expected_fees = gross * 0.029  # Typical Square rate ~2.9%
        excess_fees = fees - expected_fees
        
        print(f"\nFee Analysis:")
        print(f"Expected Fees (2.9%): ${expected_fees:,.2f}")
        print(f"Actual Fees: ${fees:,.2f}")
        print(f"Excess Fees: ${excess_fees:,.2f}")
        
        if excess_fees > 1000:
            print(f"🔍 Excess fees may include automatic loan repayments")
    
    # 4. Final Reconciliation
    outstanding_balance = total_loans - total_payments
    
    print(f"\n" + "="*60)
    print(f"FINAL SQUARE CAPITAL RECONCILIATION")
    print(f"="*60)
    print(f"📈 Total Loans Received:    ${total_loans:,.2f}")
    print(f"💸 Total Payments Made:     ${total_payments:,.2f}")
    print(f"📊 Outstanding Balance:     ${outstanding_balance:,.2f}")
    
    if outstanding_balance > 50000:
        print(f"\n[WARN]  Large outstanding balance detected!")
        print(f"   This suggests loan repayments may be embedded in")
        print(f"   Square processing fees rather than separate debits.")
    
    # 5. Loan Details Summary
    print(f"\n📋 LOAN SUMMARY:")
    print(f"-" * 30)
    if len(loan_deposits) >= 2:
        loan1_date, loan1_account, loan1_desc, loan1_amount = loan_deposits[0]
        loan2_date, loan2_account, loan2_desc, loan2_amount = loan_deposits[1]
        
        print(f"Loan #1 (CAP1622): ${loan1_amount:,.2f} on {loan1_date}")
        print(f"Loan #2 (CAP9152): ${loan2_amount:,.2f} on {loan2_date}")
    
    print(f"\n💡 RECOMMENDATIONS:")
    print(f"1. Check Square dashboard for loan repayment schedule")
    print(f"2. Monitor daily Square deposits for automatic deductions")
    print(f"3. Exclude loan deposits from revenue reconciliation")
    print(f"4. Track loan repayments separately from processing fees")
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()