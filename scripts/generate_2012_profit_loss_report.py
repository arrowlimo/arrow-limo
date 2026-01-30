#!/usr/bin/env python3
"""
Generate 2012 Profit & Loss Report - Did we make enough to pay what we owe?
Analyzes 2012 income vs expenses vs liabilities to determine financial health.
"""

import psycopg2
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def format_currency(amount):
    """Format currency with proper sign."""
    if amount is None:
        return "$0.00"
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("2012 PROFIT & LOSS REPORT - Financial Health Analysis")
    print("="*80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. INCOME ANALYSIS
    print("\n" + "="*80)
    print("1. INCOME (Revenue)")
    print("="*80)
    
    # Charter income from charters table
    cur.execute("""
        SELECT 
            COUNT(*) as charter_count,
            SUM(total_amount_due) as total_revenue,
            SUM(paid_amount) as total_paid,
            SUM(balance) as outstanding_balance
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) = 2012
    """)
    
    charter_row = cur.fetchone()
    charter_count = charter_row[0] or 0
    charter_revenue = float(charter_row[1]) if charter_row[1] else 0
    charter_paid = float(charter_row[2]) if charter_row[2] else 0
    charter_balance = float(charter_row[3]) if charter_row[3] else 0
    
    print(f"\nCharter Services:")
    print(f"  Charters completed: {charter_count:,}")
    print(f"  Total revenue: {format_currency(charter_revenue)}")
    print(f"  Collected: {format_currency(charter_paid)}")
    print(f"  Outstanding: {format_currency(charter_balance)}")
    
    # Income from receipts (4000-4999 range)
    cur.execute("""
        SELECT 
            gl_account_code,
            a.account_name,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts r
        LEFT JOIN chart_of_accounts a ON r.gl_account_code = a.account_code
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        AND gl_account_code ~ '^4'
        GROUP BY gl_account_code, a.account_name
        ORDER BY gl_account_code
    """)
    
    other_income = 0
    income_categories = []
    
    print(f"\nOther Income:")
    for row in cur.fetchall():
        code = row[0]
        name = row[1] or 'Unknown'
        count = row[2]
        amount = float(row[3]) if row[3] else 0
        income_categories.append((code, name, count, amount))
        other_income += amount
        print(f"  {code} - {name}: {format_currency(amount)} ({count} receipts)")
    
    total_income = charter_revenue + other_income
    
    print(f"\n{'='*40}")
    print(f"TOTAL INCOME: {format_currency(total_income)}")
    print(f"{'='*40}")
    
    # 2. EXPENSES ANALYSIS
    print("\n" + "="*80)
    print("2. EXPENSES")
    print("="*80)
    
    # Expenses from receipts (5000-5999 range)
    cur.execute("""
        SELECT 
            SUBSTRING(gl_account_code FROM 1 FOR 2) as category_prefix,
            CASE 
                WHEN gl_account_code ~ '^51' THEN 'Vehicle Operations'
                WHEN gl_account_code ~ '^52' THEN 'Payroll & Labor'
                WHEN gl_account_code ~ '^53' THEN 'Occupancy & Insurance'
                WHEN gl_account_code ~ '^54' THEN 'Office & Administrative'
                WHEN gl_account_code ~ '^55' THEN 'Professional Services'
                WHEN gl_account_code ~ '^56' THEN 'Marketing & Promotion'
                WHEN gl_account_code ~ '^57' THEN 'Bank & Financial'
                WHEN gl_account_code ~ '^58' THEN 'Other Operating'
                ELSE 'Uncategorized'
            END as category_name,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        AND gl_account_code ~ '^5'
        GROUP BY category_prefix, category_name
        ORDER BY category_prefix
    """)
    
    total_expenses = 0
    expense_categories = []
    
    for row in cur.fetchall():
        prefix = row[0]
        name = row[1]
        count = row[2]
        amount = float(row[3]) if row[3] else 0
        expense_categories.append((prefix, name, count, amount))
        total_expenses += amount
        print(f"  {prefix}00s - {name}: {format_currency(amount)} ({count} receipts)")
    
    # Driver payroll from driver_payroll table
    cur.execute("""
        SELECT 
            COUNT(*) as entry_count,
            SUM(gross_pay) as total_gross,
            SUM(net_pay) as total_net
        FROM driver_payroll
        WHERE year = 2012
        AND (payroll_class = 'WAGE' OR payroll_class IS NULL)
    """)
    
    payroll_row = cur.fetchone()
    if payroll_row and payroll_row[0]:
        payroll_count = payroll_row[0]
        payroll_gross = float(payroll_row[1]) if payroll_row[1] else 0
        payroll_net = float(payroll_row[2]) if payroll_row[2] else 0
        
        print(f"\n  Payroll (from driver_payroll):")
        print(f"    Entries: {payroll_count:,}")
        print(f"    Gross pay: {format_currency(payroll_gross)}")
        print(f"    Net pay: {format_currency(payroll_net)}")
        
        total_expenses += payroll_gross
    
    print(f"\n{'='*40}")
    print(f"TOTAL EXPENSES: {format_currency(total_expenses)}")
    print(f"{'='*40}")
    
    # 3. NET PROFIT/LOSS
    print("\n" + "="*80)
    print("3. NET PROFIT / (LOSS)")
    print("="*80)
    
    net_profit = total_income - total_expenses
    profit_margin = (net_profit / total_income * 100) if total_income > 0 else 0
    
    print(f"\n  Total Income:    {format_currency(total_income)}")
    print(f"  Total Expenses: -{format_currency(total_expenses)}")
    print(f"  {'─'*40}")
    
    if net_profit >= 0:
        print(f"  NET PROFIT:      {format_currency(net_profit)} ✓")
        print(f"  Profit Margin:   {profit_margin:.1f}%")
    else:
        print(f"  NET LOSS:       ({format_currency(abs(net_profit))}) ⚠️")
        print(f"  Loss Margin:     {profit_margin:.1f}%")
    
    # 4. LIABILITIES ANALYSIS - What we owe
    print("\n" + "="*80)
    print("4. LIABILITIES - What We Owe (as of Dec 31, 2012)")
    print("="*80)
    
    # Get liabilities from banking transactions (account 8314462 - vehicle loans)
    cur.execute("""
        SELECT 
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits
        FROM banking_transactions
        WHERE account_number = '8314462'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    
    vehicle_loan_row = cur.fetchone()
    if vehicle_loan_row and (vehicle_loan_row[0] or vehicle_loan_row[1]):
        loan_debits = float(vehicle_loan_row[0]) if vehicle_loan_row[0] else 0
        loan_credits = float(vehicle_loan_row[1]) if vehicle_loan_row[1] else 0
        loan_balance = loan_credits - loan_debits  # Credits = what we borrowed, Debits = what we paid
        
        print(f"\nVehicle Loans (Account 8314462):")
        print(f"  Loan advances: {format_currency(loan_credits)}")
        print(f"  Payments made: {format_currency(loan_debits)}")
        print(f"  Outstanding: {format_currency(loan_balance)}")
    else:
        loan_balance = 0
        print(f"\nVehicle Loans: No activity in 2012")
    
    # Get outstanding charter balances
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            SUM(balance) as total_owed_to_us
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) = 2012
        AND balance > 0
    """)
    
    ar_row = cur.fetchone()
    ar_count = ar_row[0] or 0
    ar_balance = float(ar_row[1]) if ar_row[1] else 0
    
    print(f"\nAccounts Receivable (Customers owe us):")
    print(f"  Outstanding charters: {ar_count:,}")
    print(f"  Amount due to us: {format_currency(ar_balance)}")
    
    # Check for liabilities in receipts (2000-2999 range)
    cur.execute("""
        SELECT 
            gl_account_code,
            a.account_name,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts r
        LEFT JOIN chart_of_accounts a ON r.gl_account_code = a.account_code
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        AND gl_account_code ~ '^2'
        GROUP BY gl_account_code, a.account_name
        ORDER BY gl_account_code
    """)
    
    liability_receipts = 0
    print(f"\nOther Liabilities (from receipts):")
    for row in cur.fetchall():
        code = row[0]
        name = row[1] or 'Unknown'
        count = row[2]
        amount = float(row[3]) if row[3] else 0
        liability_receipts += amount
        print(f"  {code} - {name}: {format_currency(amount)} ({count} receipts)")
    
    total_liabilities = loan_balance + liability_receipts
    
    print(f"\n{'='*40}")
    print(f"TOTAL LIABILITIES: {format_currency(total_liabilities)}")
    print(f"{'='*40}")
    
    # 5. FINANCIAL HEALTH ASSESSMENT
    print("\n" + "="*80)
    print("5. FINANCIAL HEALTH ASSESSMENT")
    print("="*80)
    
    print(f"\nCan we pay what we owe?")
    print(f"  Net Profit 2012: {format_currency(net_profit)}")
    print(f"  Total Liabilities: {format_currency(total_liabilities)}")
    print(f"  Accounts Receivable (owed to us): {format_currency(ar_balance)}")
    
    available_cash = net_profit + ar_balance
    
    print(f"\n  Available Resources: {format_currency(available_cash)}")
    print(f"  {'─'*40}")
    
    if available_cash >= total_liabilities:
        surplus = available_cash - total_liabilities
        print(f"  SURPLUS: {format_currency(surplus)} ✓")
        print(f"\n  ✓ YES - We made enough to pay what we owe")
        print(f"  Financial position: HEALTHY")
        if surplus > 0:
            coverage_ratio = available_cash / total_liabilities if total_liabilities > 0 else float('inf')
            print(f"  Coverage ratio: {coverage_ratio:.2f}x")
    else:
        shortfall = total_liabilities - available_cash
        print(f"  SHORTFALL: {format_currency(shortfall)} ⚠️")
        print(f"\n  ⚠️  NO - We need additional {format_currency(shortfall)} to cover liabilities")
        print(f"  Financial position: STRETCHED")
    
    # 6. KEY METRICS
    print("\n" + "="*80)
    print("6. KEY FINANCIAL METRICS")
    print("="*80)
    
    # Operating expense ratio
    operating_expense_ratio = (total_expenses / total_income * 100) if total_income > 0 else 0
    print(f"\n  Operating Expense Ratio: {operating_expense_ratio:.1f}%")
    
    # Collection rate
    collection_rate = (charter_paid / charter_revenue * 100) if charter_revenue > 0 else 0
    print(f"  Collection Rate: {collection_rate:.1f}%")
    
    # Average revenue per charter
    avg_revenue = charter_revenue / charter_count if charter_count > 0 else 0
    print(f"  Average Revenue per Charter: {format_currency(avg_revenue)}")
    
    # Debt to income ratio
    debt_to_income = (total_liabilities / total_income * 100) if total_income > 0 else 0
    print(f"  Debt-to-Income Ratio: {debt_to_income:.1f}%")
    
    print("\n" + "="*80)
    print("✓ REPORT COMPLETE")
    print("="*80)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
