"""
Comprehensive Financial Reports Generator

Generates all standard QuickBooks-style reports for financial oversight:
- Journal Report
- General Ledger Report  
- Profit & Loss (Income Statement)
- Balance Sheet
- Outstanding Balance Report (A/R Aging)
- Accounts Payable Aging
- Creditor Report
- Vehicle Loan Report
- Employee Records Report
- Vehicle Maintenance Report
- Vehicle Fuel Report
- Asset Depreciation Report
- Write-off Report
- Trial Balance

All reports support date range filtering and export to CSV/Excel.
"""

import psycopg2
import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import sys


def get_db_connection():
    """Connect to almsdata database"""
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )


def format_currency(amount):
    """Format amount as currency"""
    if amount is None:
        return "$0.00"
    return f"${amount:,.2f}"


def generate_journal_report(conn, start_date=None, end_date=None):
    """
    Journal Report - All transactions in chronological order
    QuickBooks equivalent: Transaction Detail by Account
    """
    print("\n" + "=" * 80)
    print("JOURNAL REPORT")
    print("=" * 80)
    
    query = """
        SELECT 
            date,
            transaction_type,
            num,
            name,
            account_name,
            account,
            memo_description,
            supplier,
            employee,
            customer,
            debit,
            credit,
            balance
        FROM general_ledger
        WHERE 1=1
    """
    
    params = []
    if start_date:
        query += " AND date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND date <= %s"
        params.append(end_date)
    
    query += " ORDER BY date, id"
    
    df = pd.read_sql_query(query, conn, params=params)
    
    print(f"\nDate Range: {start_date or 'Beginning'} to {end_date or 'Present'}")
    print(f"Total Transactions: {len(df):,}")
    print(f"Total Debits: {format_currency(df['debit'].sum())}")
    print(f"Total Credits: {format_currency(df['credit'].sum())}")
    
    return df


def generate_general_ledger_report(conn, start_date=None, end_date=None, account_filter=None):
    """
    General Ledger Report - Transactions grouped by account
    QuickBooks equivalent: General Ledger
    """
    print("\n" + "=" * 80)
    print("GENERAL LEDGER REPORT")
    print("=" * 80)
    
    query = """
        SELECT 
            account_name,
            account,
            date,
            transaction_type,
            num,
            name,
            memo_description,
            supplier,
            debit,
            credit,
            balance
        FROM general_ledger
        WHERE 1=1
    """
    
    params = []
    if start_date:
        query += " AND date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND date <= %s"
        params.append(end_date)
    if account_filter:
        query += " AND account_name ILIKE %s"
        params.append(f"%{account_filter}%")
    
    query += " ORDER BY account_name, date, id"
    
    df = pd.read_sql_query(query, conn, params=params)
    
    print(f"\nDate Range: {start_date or 'Beginning'} to {end_date or 'Present'}")
    print(f"Accounts Included: {df['account_name'].nunique():,}")
    print(f"Total Transactions: {len(df):,}")
    
    # Summary by account
    account_summary = df.groupby('account_name').agg({
        'debit': 'sum',
        'credit': 'sum'
    }).reset_index()
    account_summary['balance'] = account_summary['debit'] - account_summary['credit']
    
    print(f"\nAccount Summary (Top 10 by Balance):")
    for _, row in account_summary.nlargest(10, 'balance').iterrows():
        print(f"  {row['account_name']:50} {format_currency(row['balance'])}")
    
    return df


def generate_profit_loss_report(conn, start_date=None, end_date=None):
    """
    Profit & Loss Report (Income Statement)
    QuickBooks equivalent: Profit & Loss
    """
    print("\n" + "=" * 80)
    print("PROFIT & LOSS REPORT (INCOME STATEMENT)")
    print("=" * 80)
    
    query = """
        SELECT 
            account_name,
            account_type,
            SUM(debit) as total_debit,
            SUM(credit) as total_credit
        FROM general_ledger
        WHERE account_type IN ('Income', 'Expense', 'Cost of Goods Sold', 'Other Income', 'Other Expense')
    """
    
    params = []
    if start_date:
        query += " AND date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND date <= %s"
        params.append(end_date)
    
    query += " GROUP BY account_name, account_type ORDER BY account_type, account_name"
    
    df = pd.read_sql_query(query, conn, params=params)
    
    print(f"\nPeriod: {start_date or 'Beginning'} to {end_date or 'Present'}")
    
    # Calculate income and expenses
    income = df[df['account_type'].str.contains('Income', case=False, na=False)]
    expenses = df[df['account_type'].str.contains('Expense', case=False, na=False)]
    cogs = df[df['account_type'].str.contains('Cost', case=False, na=False)]
    
    total_income = income['total_credit'].sum() - income['total_debit'].sum()
    total_cogs = cogs['total_debit'].sum() - cogs['total_credit'].sum()
    total_expenses = expenses['total_debit'].sum() - expenses['total_credit'].sum()
    
    gross_profit = total_income - total_cogs
    net_income = gross_profit - total_expenses
    
    print(f"\nINCOME:")
    print(f"  Total Income:          {format_currency(total_income)}")
    if total_cogs > 0:
        print(f"  Cost of Goods Sold:    {format_currency(total_cogs)}")
        print(f"  Gross Profit:          {format_currency(gross_profit)}")
    
    print(f"\nEXPENSES:")
    print(f"  Total Expenses:        {format_currency(total_expenses)}")
    
    print(f"\nNET INCOME (LOSS):       {format_currency(net_income)}")
    
    if total_income > 0:
        print(f"Net Profit Margin:      {(net_income / total_income * 100):.2f}%")
    
    return df


def generate_balance_sheet_report(conn, as_of_date=None):
    """
    Balance Sheet Report
    QuickBooks equivalent: Balance Sheet
    """
    print("\n" + "=" * 80)
    print("BALANCE SHEET")
    print("=" * 80)
    
    if as_of_date is None:
        as_of_date = datetime.now().date()
    
    query = """
        SELECT 
            account_name,
            account_type,
            SUM(debit) as total_debit,
            SUM(credit) as total_credit
        FROM general_ledger
        WHERE date <= %s
        GROUP BY account_name, account_type
        HAVING SUM(debit) - SUM(credit) != 0
        ORDER BY account_type, account_name
    """
    
    df = pd.read_sql_query(query, conn, params=(as_of_date,))
    df['balance'] = df['total_debit'] - df['total_credit']
    
    print(f"\nAs of: {as_of_date}")
    
    # Assets
    assets = df[df['account_type'].str.contains('Asset', case=False, na=False)]
    total_assets = assets['balance'].sum()
    
    # Liabilities
    liabilities = df[df['account_type'].str.contains('Liability|Payable', case=False, na=False)]
    total_liabilities = -liabilities['balance'].sum()  # Liabilities are negative
    
    # Equity
    equity = df[df['account_type'].str.contains('Equity', case=False, na=False)]
    total_equity = -equity['balance'].sum()  # Equity is negative
    
    print(f"\nASSETS:")
    print(f"  Total Assets:          {format_currency(total_assets)}")
    
    print(f"\nLIABILITIES:")
    print(f"  Total Liabilities:     {format_currency(total_liabilities)}")
    
    print(f"\nEQUITY:")
    print(f"  Total Equity:          {format_currency(total_equity)}")
    
    print(f"\nTOTAL LIABILITIES + EQUITY: {format_currency(total_liabilities + total_equity)}")
    print(f"\nBalance Check: {format_currency(total_assets - (total_liabilities + total_equity))}")
    
    return df


def generate_ar_aging_report(conn, as_of_date=None):
    """
    Accounts Receivable Aging Report
    QuickBooks equivalent: A/R Aging Summary
    """
    print("\n" + "=" * 80)
    print("ACCOUNTS RECEIVABLE AGING REPORT")
    print("=" * 80)
    
    if as_of_date is None:
        as_of_date = datetime.now().date()
    
    query = """
        SELECT * FROM client_aging_report
    """
    
    df = pd.read_sql_query(query, conn)
    
    print(f"\nAs of: {as_of_date}")
    print(f"Total Outstanding: {format_currency(df['total_outstanding'].sum())}")
    print(f"Clients with Balance: {len(df)}")
    
    # Age buckets
    print(f"\nAge Breakdown:")
    print(f"  Current (0-30):        {format_currency(df['current'].sum())}")
    print(f"  31-60 days:            {format_currency(df['days_31_60'].sum())}")
    print(f"  61-90 days:            {format_currency(df['days_61_90'].sum())}")
    print(f"  Over 90 days:          {format_currency(df['over_90'].sum())}")
    
    return df


def generate_ap_aging_report(conn, as_of_date=None):
    """
    Accounts Payable Aging Report
    QuickBooks equivalent: A/P Aging Summary
    """
    print("\n" + "=" * 80)
    print("ACCOUNTS PAYABLE AGING REPORT")
    print("=" * 80)
    
    if as_of_date is None:
        as_of_date = datetime.now().date()
    
    query = """
        SELECT 
            supplier,
            COUNT(*) as bill_count,
            SUM(credit - debit) as amount_due,
            MIN(date) as oldest_bill,
            MAX(date) as newest_bill,
            CURRENT_DATE - MAX(date) as days_outstanding
        FROM general_ledger
        WHERE supplier IS NOT NULL
          AND credit > debit
          AND date <= %s
        GROUP BY supplier
        HAVING SUM(credit - debit) > 0
        ORDER BY amount_due DESC
    """
    
    df = pd.read_sql_query(query, conn, params=(as_of_date,))
    
    print(f"\nAs of: {as_of_date}")
    print(f"Total Payable: {format_currency(df['amount_due'].sum())}")
    print(f"Vendors with Balance: {len(df)}")
    
    print(f"\nTop 10 Vendors by Amount Due:")
    for _, row in df.head(10).iterrows():
        print(f"  {row['supplier']:40} {format_currency(row['amount_due'])}")
    
    return df


def generate_creditor_report(conn):
    """
    Creditor Report - All vendors and suppliers with transaction history
    QuickBooks equivalent: Vendor Contact List + Transaction History
    """
    print("\n" + "=" * 80)
    print("CREDITOR REPORT")
    print("=" * 80)
    
    query = """
        SELECT 
            supplier,
            COUNT(*) as transaction_count,
            MIN(date) as first_transaction,
            MAX(date) as last_transaction,
            SUM(debit) as total_purchases,
            SUM(credit) as total_payments,
            SUM(credit - debit) as current_balance
        FROM general_ledger
        WHERE supplier IS NOT NULL
        GROUP BY supplier
        ORDER BY total_purchases DESC
    """
    
    df = pd.read_sql_query(query, conn)
    
    print(f"\nTotal Vendors: {len(df)}")
    print(f"Total Purchases: {format_currency(df['total_purchases'].sum())}")
    print(f"Total Payments: {format_currency(df['total_payments'].sum())}")
    print(f"Outstanding Balance: {format_currency(df['current_balance'].sum())}")
    
    print(f"\nTop 10 Vendors by Purchase Volume:")
    for _, row in df.head(10).iterrows():
        print(f"  {row['supplier']:40} {format_currency(row['total_purchases'])}")
    
    return df


def generate_vehicle_loan_report(conn):
    """
    Vehicle Loan Report - All vehicle financing with balances
    Uses v_loan_dashboard_summary view
    """
    print("\n" + "=" * 80)
    print("VEHICLE LOAN REPORT")
    print("=" * 80)
    
    query = """
        SELECT * FROM v_loan_dashboard_summary
        ORDER BY loan_status, current_balance DESC
    """
    
    df = pd.read_sql_query(query, conn)
    
    print(f"\nTotal Loans: {len(df)}")
    print(f"Active Loans: {len(df[df['loan_status'] == 'ACTIVE'])}")
    print(f"Total Balance: {format_currency(df['current_balance'].sum())}")
    print(f"Monthly Payment: {format_currency(df['monthly_payment'].sum())}")
    
    print(f"\nActive Loans:")
    for _, row in df[df['loan_status'] == 'ACTIVE'].iterrows():
        print(f"  {row['vehicle_name']:30} {format_currency(row['current_balance']):>15} @ {row['interest_rate']:.2f}%")
    
    return df


def generate_employee_report(conn):
    """
    Employee Records Report - All employees with transaction history
    """
    print("\n" + "=" * 80)
    print("EMPLOYEE RECORDS REPORT")
    print("=" * 80)
    
    query = """
        SELECT 
            employee,
            COUNT(*) as transaction_count,
            MIN(date) as first_transaction,
            MAX(date) as last_transaction,
            SUM(debit) as total_paid,
            SUM(credit) as total_deductions,
            EXTRACT(YEAR FROM MAX(date)) - EXTRACT(YEAR FROM MIN(date)) as years_employed
        FROM general_ledger
        WHERE employee IS NOT NULL
        GROUP BY employee
        ORDER BY first_transaction
    """
    
    df = pd.read_sql_query(query, conn)
    
    print(f"\nTotal Employees: {len(df)}")
    print(f"Total Payroll: {format_currency(df['total_paid'].sum())}")
    
    print(f"\nEmployee Summary:")
    for _, row in df.iterrows():
        print(f"  {row['employee']:40} Transactions: {row['transaction_count']:>5}  Paid: {format_currency(row['total_paid'])}")
    
    return df


def generate_vehicle_maintenance_report(conn, start_date=None, end_date=None):
    """
    Vehicle Maintenance Report
    """
    print("\n" + "=" * 80)
    print("VEHICLE MAINTENANCE REPORT")
    print("=" * 80)
    
    query = """
        SELECT * FROM vehicle_maintenance_dashboard
        ORDER BY vehicle_name, last_service_date DESC
    """
    
    df = pd.read_sql_query(query, conn)
    
    print(f"\nTotal Vehicles: {len(df)}")
    print(f"Overdue Services: {len(df[df['service_status'] == 'OVERDUE'])}")
    print(f"Due Soon: {len(df[df['service_status'] == 'DUE SOON'])}")
    
    print(f"\nMaintenance Status:")
    for _, row in df.iterrows():
        print(f"  {row['vehicle_name']:20} Last Service: {row['last_service_date']}  Status: {row['service_status']}")
    
    return df


def generate_vehicle_fuel_report(conn, start_date=None, end_date=None):
    """
    Vehicle Fuel Report
    """
    print("\n" + "=" * 80)
    print("VEHICLE FUEL REPORT")
    print("=" * 80)
    
    query = """
        SELECT 
            vehicle_id,
            COUNT(*) as fillup_count,
            SUM(amount) as total_fuel_cost,
            AVG(amount) as avg_fillup_cost,
            MIN(recorded_at) as first_fillup,
            MAX(recorded_at) as last_fillup
        FROM vehicle_fuel_log
        WHERE 1=1
    """
    
    params = []
    if start_date:
        query += " AND recorded_at >= %s"
        params.append(start_date)
    if end_date:
        query += " AND recorded_at <= %s"
        params.append(end_date)
    
    query += " GROUP BY vehicle_id ORDER BY total_fuel_cost DESC"
    
    df = pd.read_sql_query(query, conn, params=params)
    
    print(f"\nDate Range: {start_date or 'Beginning'} to {end_date or 'Present'}")
    print(f"Total Fuel Cost: {format_currency(df['total_fuel_cost'].sum())}")
    print(f"Total Fillups: {df['fillup_count'].sum()}")
    
    print(f"\nFuel Cost by Vehicle:")
    for _, row in df.iterrows():
        print(f"  {row['vehicle_id']:20} Fillups: {row['fillup_count']:>3}  Total: {format_currency(row['total_fuel_cost']):>12}  Avg: {format_currency(row['avg_fillup_cost'])}")
    
    return df


def generate_asset_depreciation_report(conn, as_of_date=None):
    """
    Asset Depreciation Report
    """
    print("\n" + "=" * 80)
    print("ASSET DEPRECIATION REPORT")
    print("=" * 80)
    
    if as_of_date is None:
        as_of_date = datetime.now().date()
    
    query = """
        SELECT * FROM asset_depreciation_schedule
        WHERE depreciation_end_date >= %s OR depreciation_end_date IS NULL
        ORDER BY asset_name
    """
    
    df = pd.read_sql_query(query, conn, params=(as_of_date,))
    
    print(f"\nAs of: {as_of_date}")
    print(f"Total Assets: {len(df)}")
    print(f"Original Cost: {format_currency(df['original_cost'].sum())}")
    print(f"Accumulated Depreciation: {format_currency(df['accumulated_depreciation'].sum())}")
    print(f"Net Book Value: {format_currency(df['net_book_value'].sum())}")
    
    print(f"\nAsset Summary:")
    for _, row in df.iterrows():
        print(f"  {row['asset_name']:40} NBV: {format_currency(row['net_book_value']):>12}  Method: {row['depreciation_method']}")
    
    return df


def generate_writeoff_report(conn, start_date=None, end_date=None):
    """
    Write-off Report - Bad debts and losses
    """
    print("\n" + "=" * 80)
    print("WRITE-OFF REPORT")
    print("=" * 80)
    
    query = """
        SELECT 
            date,
            transaction_type,
            name,
            account_name,
            memo_description,
            debit,
            credit,
            supplier,
            customer
        FROM general_ledger
        WHERE (
            account_name ILIKE '%bad debt%' 
            OR account_name ILIKE '%write%off%'
            OR account_name ILIKE '%loss%'
            OR memo_description ILIKE '%write%off%'
            OR memo_description ILIKE '%bad debt%'
        )
    """
    
    params = []
    if start_date:
        query += " AND date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND date <= %s"
        params.append(end_date)
    
    query += " ORDER BY date DESC"
    
    df = pd.read_sql_query(query, conn, params=params)
    
    print(f"\nDate Range: {start_date or 'Beginning'} to {end_date or 'Present'}")
    print(f"Total Write-offs: {len(df)}")
    print(f"Total Amount: {format_currency(df['debit'].sum())}")
    
    if len(df) > 0:
        print(f"\nRecent Write-offs:")
        for _, row in df.head(20).iterrows():
            print(f"  {row['date']} {row['name']:30} {format_currency(row['debit']):>12}  {row['memo_description']}")
    else:
        print("\nNo write-offs found.")
    
    return df


def generate_trial_balance(conn, as_of_date=None):
    """
    Trial Balance Report
    QuickBooks equivalent: Trial Balance
    """
    print("\n" + "=" * 80)
    print("TRIAL BALANCE")
    print("=" * 80)
    
    if as_of_date is None:
        as_of_date = datetime.now().date()
    
    query = """
        SELECT 
            account_name,
            account_type,
            SUM(debit) as total_debit,
            SUM(credit) as total_credit,
            SUM(debit) - SUM(credit) as balance
        FROM general_ledger
        WHERE date <= %s
        GROUP BY account_name, account_type
        HAVING SUM(debit) - SUM(credit) != 0
        ORDER BY account_type, account_name
    """
    
    df = pd.read_sql_query(query, conn, params=(as_of_date,))
    
    print(f"\nAs of: {as_of_date}")
    print(f"Total Accounts: {len(df)}")
    
    total_debits = df['total_debit'].sum()
    total_credits = df['total_credit'].sum()
    
    print(f"\nTotal Debits:  {format_currency(total_debits)}")
    print(f"Total Credits: {format_currency(total_credits)}")
    print(f"Difference:    {format_currency(total_debits - total_credits)}")
    
    if abs(total_debits - total_credits) < 0.01:
        print("\n✓ Books are in balance!")
    else:
        print("\n⚠ Warning: Books are out of balance!")
    
    return df


def export_to_excel(report_name, df, output_dir="L:\\limo\\reports"):
    """Export report to Excel"""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    filename = f"{report_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = output_path / filename
    
    df.to_excel(filepath, index=False, engine='openpyxl')
    print(f"\n📄 Exported to: {filepath}")
    
    return filepath


def main():
    print("=" * 80)
    print(" " * 20 + "COMPREHENSIVE FINANCIAL REPORTS")
    print("=" * 80)
    
    # Date ranges
    today = datetime.now().date()
    start_of_year = datetime(today.year, 1, 1).date()
    start_of_month = datetime(today.year, today.month, 1).date()
    
    conn = get_db_connection()
    
    try:
        print("\nGenerating all financial reports...")
        print("\nDate Options:")
        print("  1. Year-to-Date (YTD)")
        print("  2. Month-to-Date (MTD)")
        print("  3. All Time")
        print("  4. Custom Range")
        
        choice = input("\nSelect date range (1-4) [1]: ").strip() or "1"
        
        if choice == "1":
            start_date = start_of_year
            end_date = today
            print(f"\nUsing YTD: {start_date} to {end_date}")
        elif choice == "2":
            start_date = start_of_month
            end_date = today
            print(f"\nUsing MTD: {start_date} to {end_date}")
        elif choice == "3":
            start_date = None
            end_date = None
            print(f"\nUsing All Time")
        else:
            start_input = input("Start date (YYYY-MM-DD): ").strip()
            end_input = input("End date (YYYY-MM-DD): ").strip()
            start_date = datetime.strptime(start_input, "%Y-%m-%d").date() if start_input else None
            end_date = datetime.strptime(end_input, "%Y-%m-%d").date() if end_input else None
        
        # Generate reports
        reports = []
        
        # 1. Journal Report
        df = generate_journal_report(conn, start_date, end_date)
        reports.append(("Journal_Report", df))
        
        # 2. General Ledger
        df = generate_general_ledger_report(conn, start_date, end_date)
        reports.append(("General_Ledger", df))
        
        # 3. Profit & Loss
        df = generate_profit_loss_report(conn, start_date, end_date)
        reports.append(("Profit_Loss", df))
        
        # 4. Balance Sheet
        df = generate_balance_sheet_report(conn, end_date or today)
        reports.append(("Balance_Sheet", df))
        
        # 5. Trial Balance
        df = generate_trial_balance(conn, end_date or today)
        reports.append(("Trial_Balance", df))
        
        # 6. A/R Aging
        df = generate_ar_aging_report(conn, end_date or today)
        reports.append(("AR_Aging", df))
        
        # 7. A/P Aging
        df = generate_ap_aging_report(conn, end_date or today)
        reports.append(("AP_Aging", df))
        
        # 8. Creditor Report
        df = generate_creditor_report(conn)
        reports.append(("Creditor_Report", df))
        
        # 9. Vehicle Loans
        df = generate_vehicle_loan_report(conn)
        reports.append(("Vehicle_Loans", df))
        
        # 10. Employee Records
        df = generate_employee_report(conn)
        reports.append(("Employee_Records", df))
        
        # 11. Vehicle Maintenance
        df = generate_vehicle_maintenance_report(conn, start_date, end_date)
        reports.append(("Vehicle_Maintenance", df))
        
        # 12. Vehicle Fuel
        df = generate_vehicle_fuel_report(conn, start_date, end_date)
        reports.append(("Vehicle_Fuel", df))
        
        # 13. Asset Depreciation
        df = generate_asset_depreciation_report(conn, end_date or today)
        reports.append(("Asset_Depreciation", df))
        
        # 14. Write-offs
        df = generate_writeoff_report(conn, start_date, end_date)
        reports.append(("Write_Offs", df))
        
        # Export all reports
        print("\n" + "=" * 80)
        print("EXPORTING REPORTS TO EXCEL")
        print("=" * 80)
        
        export_choice = input("\nExport all reports to Excel? (y/n) [y]: ").strip().lower() or "y"
        
        if export_choice == "y":
            for report_name, report_df in reports:
                export_to_excel(report_name, report_df)
        
        print("\n" + "=" * 80)
        print("[OK] ALL REPORTS GENERATED SUCCESSFULLY")
        print("=" * 80)
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
