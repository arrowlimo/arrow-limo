#!/usr/bin/env python3
"""
Generate CORRECTED 2012 Profit & Loss Report.
Uses proper categorized expenses from receipts table.
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("2012 CORRECTED PROFIT & LOSS REPORT")
    print("="*80)
    print("Methodology: Banking-based with proper GL categorization")
    print("="*80)
    
    # INCOME
    print("\n" + "="*80)
    print("INCOME")
    print("="*80)
    
    # Charter revenue
    cur.execute("""
        SELECT 
            COUNT(*) as charter_count,
            SUM(total_amount_due) as total_revenue,
            SUM(paid_amount) as collected,
            SUM(balance) as outstanding
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) = 2012
        AND cancelled = FALSE
    """)
    
    charter_data = cur.fetchone()
    charter_count = charter_data[0]
    charter_revenue = float(charter_data[1] or 0)
    charter_collected = float(charter_data[2] or 0)
    charter_outstanding = float(charter_data[3] or 0)
    
    print(f"\n4100 Charter Revenue:")
    print(f"  {charter_count:,} charters = ${charter_revenue:,.2f}")
    print(f"  Collected: ${charter_collected:,.2f} ({charter_collected/charter_revenue*100:.1f}%)")
    print(f"  Outstanding: ${charter_outstanding:,.2f}")
    
    # Other income (account 4000-4999)
    cur.execute("""
        SELECT 
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_income
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        AND gl_account_code ~ '^4'
    """)
    
    other_income = cur.fetchone()
    other_count = other_income[0]
    other_amount = float(other_income[1] or 0)
    
    print(f"\n4000-4999 Other Income:")
    print(f"  {other_count:,} receipts = ${other_amount:,.2f}")
    
    total_income = charter_revenue + other_amount
    print(f"\n{'='*80}")
    print(f"TOTAL INCOME: ${total_income:,.2f}")
    print(f"{'='*80}")
    
    # EXPENSES BY CATEGORY
    print("\n" + "="*80)
    print("EXPENSES (FROM RECEIPTS)")
    print("="*80)
    
    cur.execute("""
        SELECT 
            gl_account_code,
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_amount
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        AND gl_account_code ~ '^5'
        GROUP BY gl_account_code
        ORDER BY gl_account_code
    """)
    
    expenses = cur.fetchall()
    total_expenses = 0
    
    expense_names = {
        '5110': 'Fuel',
        '5120': 'Vehicle Maintenance/Repairs',
        '5130': 'Insurance',
        '5140': 'Licenses & Permits',
        '5210': 'Payroll - Wages',
        '5320': 'Driver Meals',
        '5325': 'Business Meals & Entertainment',
        '5410': 'Rent',
        '5420': 'Office Supplies',
        '5430': 'Communication (Phone/Internet)',
        '5440': 'Utilities',
        '5510': 'Professional Fees',
        '5610': 'Advertising & Marketing',
        '5710': 'Bank Charges & Fees',
        '5720': 'Credit Card Processing Fees',
        '5820': 'Equipment Rental',
        '5850': 'Mixed Use (Uncategorized)'
    }
    
    for expense in expenses:
        gl_code = expense[0]
        count = expense[1]
        amount = float(expense[2])
        total_expenses += amount
        
        name = expense_names.get(gl_code, 'Other')
        print(f"\n{gl_code} {name}:")
        print(f"  {count:,} receipts = ${amount:,.2f} ({amount/total_income*100:.1f}% of revenue)")
    
    print(f"\n{'='*80}")
    print(f"TOTAL EXPENSES: ${total_expenses:,.2f}")
    print(f"{'='*80}")
    
    # NET PROFIT/LOSS
    net_profit = total_income - total_expenses
    margin = (net_profit / total_income * 100) if total_income > 0 else 0
    
    print("\n" + "="*80)
    print("NET PROFIT/(LOSS)")
    print("="*80)
    print(f"\nIncome:    ${total_income:12,.2f}")
    print(f"Expenses: -${total_expenses:12,.2f}")
    print(f"          {'='*14}")
    print(f"Net:       ${net_profit:12,.2f}")
    print(f"Margin:    {margin:11,.1f}%")
    
    # BANKING RECONCILIATION
    print("\n" + "="*80)
    print("BANKING RECONCILIATION")
    print("="*80)
    
    cur.execute("""
        SELECT 
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    
    banking = cur.fetchone()
    banking_debits = float(banking[0] or 0)
    banking_credits = float(banking[1] or 0)
    
    print(f"\nBanking debits (money out):  ${banking_debits:,.2f}")
    print(f"Receipt expenses:            ${total_expenses:,.2f}")
    print(f"Difference:                  ${abs(banking_debits - total_expenses):,.2f}")
    print(f"\nBanking credits (money in):  ${banking_credits:,.2f}")
    print(f"Income recognized:           ${total_income:,.2f}")
    print(f"Difference:                  ${abs(banking_credits - total_income):,.2f}")
    
    # FINAL ASSESSMENT
    print("\n" + "="*80)
    print("FINANCIAL ASSESSMENT")
    print("="*80)
    
    if net_profit < 0:
        print(f"\n⚠️  OPERATING LOSS: ${abs(net_profit):,.2f}")
        print(f"\nThis explains:")
        print(f"  • Need to refinance vehicle to cover shortfall")
        print(f"  • 79 NSF events due to negative cash flow")
        print(f"  • Barely enough money to pay bills")
    else:
        print(f"\n✓ NET PROFIT: ${net_profit:,.2f}")
    
    # Key metrics
    print(f"\nKEY METRICS:")
    print(f"  • Revenue per charter: ${charter_revenue/charter_count:,.2f}")
    print(f"  • Expenses as % of revenue: {total_expenses/total_income*100:.1f}%")
    print(f"  • Vehicle maintenance as % of revenue: {[float(e[2]) for e in expenses if e[0]=='5120'][0]/total_income*100:.1f}%")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
