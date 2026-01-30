#!/usr/bin/env python3
"""
Generate GL Coding Report for Square Capital Activity.
Categorizes all loan transactions for accounting/tax purposes.
"""

import os
import psycopg2
import csv
from datetime import datetime

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

OUTPUT_FILE = r"l:\limo\reports\square_capital_gl_coding.csv"


def generate_gl_report(conn):
    """Generate GL coding report for Square Capital activity."""
    cur = conn.cursor()
    
    print("=" * 70)
    print("SQUARE CAPITAL GL CODING REPORT")
    print("=" * 70)
    
    # Get all activity with GL coding
    cur.execute("""
        SELECT 
            activity_date,
            description,
            amount,
            CASE 
                WHEN description ILIKE '%loan deposit%' THEN 'LOAN_PROCEEDS'
                WHEN description ILIKE '%payment from%loan%' THEN 'LOAN_PAYOFF'
                WHEN description ILIKE '%automatic payment%' AND amount < 0 THEN 'LOAN_PAYMENT'
                WHEN description ILIKE '%automatic payment%' AND amount > 0 THEN 'LOAN_REFUND'
                WHEN description ILIKE '%refund%' THEN 'LOAN_REFUND'
                ELSE 'OTHER'
            END as gl_category,
            CASE 
                WHEN description ILIKE '%loan deposit%' THEN 'Bank Account (Debit) / Loan Payable (Credit)'
                WHEN description ILIKE '%payment from%loan%' THEN 'Loan Payable (Debit) / Bank Account (Credit)'
                WHEN description ILIKE '%automatic payment%' AND amount < 0 THEN 'Loan Payable (Debit) / Bank Account (Credit)'
                WHEN description ILIKE '%automatic payment%' AND amount > 0 THEN 'Bank Account (Debit) / Loan Payable (Credit)'
                WHEN description ILIKE '%refund%' THEN 'Bank Account (Debit) / Loan Payable (Credit)'
                ELSE 'Review Required'
            END as gl_entries,
            CASE 
                WHEN description ILIKE '%loan deposit%' THEN '2400 - Short Term Loan Payable'
                WHEN description ILIKE '%payment from%loan%' THEN '2400 - Short Term Loan Payable'
                WHEN description ILIKE '%automatic payment%' THEN '2400 - Short Term Loan Payable'
                WHEN description ILIKE '%refund%' THEN '2400 - Short Term Loan Payable'
                ELSE '2400 - Short Term Loan Payable'
            END as gl_account
        FROM square_capital_activity
        ORDER BY activity_date, id
    """)
    
    rows = cur.fetchall()
    
    # Write to CSV
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Date', 'Description', 'Amount', 'GL Category', 'GL Entry', 'GL Account'
        ])
        
        for row in rows:
            writer.writerow(row)
    
    print(f"\n✓ Exported {len(rows)} transactions to:")
    print(f"  {OUTPUT_FILE}")
    
    # Summary by category
    cur.execute("""
        SELECT 
            CASE 
                WHEN description ILIKE '%loan deposit%' THEN 'Loan Deposits Received'
                WHEN description ILIKE '%payment from%loan%' THEN 'Loan Payoffs (Transfers)'
                WHEN description ILIKE '%automatic payment%' AND amount < 0 THEN 'Loan Payments (Deductions)'
                WHEN description ILIKE '%automatic payment%' AND amount > 0 THEN 'Loan Payment Refunds'
                WHEN description ILIKE '%refund%' THEN 'Other Refunds'
                ELSE 'Other Transactions'
            END as category,
            COUNT(*) as count,
            SUM(amount) as total
        FROM square_capital_activity
        GROUP BY category
        ORDER BY SUM(amount) DESC
    """)
    
    print(f"\n📊 GL Category Summary:\n")
    print(f"{'Category':<35} {'Count':>8} {'Total':>15}")
    print("-" * 60)
    
    grand_total = 0
    for row in cur.fetchall():
        category, count, total = row
        print(f"{category:<35} {count:>8,} ${total:>13,.2f}")
        grand_total += total
    
    print("-" * 60)
    print(f"{'GRAND TOTAL':<35} {'':<8} ${grand_total:>13,.2f}")
    
    # Loan reconciliation
    print(f"\n💰 Loan Reconciliation:\n")
    
    cur.execute("""
        SELECT 
            SUM(CASE WHEN description ILIKE '%loan deposit%' THEN amount ELSE 0 END) as deposits,
            SUM(CASE WHEN description ILIKE '%payment from%loan%' THEN amount ELSE 0 END) as payoffs,
            SUM(CASE WHEN description ILIKE '%automatic payment%' AND amount < 0 THEN amount ELSE 0 END) as payments,
            SUM(CASE WHEN description ILIKE '%automatic payment%' AND amount > 0 THEN amount ELSE 0 END) as refunds
        FROM square_capital_activity
    """)
    
    deposits, payoffs, payments, refunds = cur.fetchone()
    
    print(f"  Loan Deposits Received:        ${deposits:>12,.2f}")
    print(f"  Loan Payoffs (Transfers Out):  ${payoffs:>12,.2f}")
    print(f"  Automatic Payments (Deducted): ${payments:>12,.2f}")
    print(f"  Payment Refunds:               ${refunds:>12,.2f}")
    print(f"  " + "-" * 40)
    
    net_loan_balance = deposits + payoffs + payments + refunds
    print(f"  Net Activity:                  ${net_loan_balance:>12,.2f}")
    
    # Compare to loan table
    cur.execute("""
        SELECT 
            SUM(loan_amount) as total_borrowed,
            COUNT(*) as loan_count
        FROM square_capital_loans
    """)
    
    total_borrowed, loan_count = cur.fetchone()
    
    print(f"\n  Loans in Database:             {loan_count} loans")
    print(f"  Total Borrowed (Database):     ${total_borrowed:>12,.2f}")
    
    cur.execute("""
        SELECT 
            SUM(payment_amount) as total_paid
        FROM square_loan_payments
    """)
    
    total_paid = cur.fetchone()[0] or 0
    
    print(f"  Total Paid (Tracked):          ${total_paid:>12,.2f}")
    print(f"  Outstanding Balance:           ${total_borrowed - total_paid:>12,.2f}")
    
    cur.close()


def main():
    print(f"Generating GL coding report...")
    print(f"Output: {OUTPUT_FILE}\n")
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    try:
        generate_gl_report(conn)
        
        print("\n" + "=" * 70)
        print("✓ GL CODING REPORT COMPLETE")
        print("=" * 70)
        print(f"\n📁 Import {OUTPUT_FILE} into your accounting system")
        print("   for GL coding and reconciliation.\n")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
