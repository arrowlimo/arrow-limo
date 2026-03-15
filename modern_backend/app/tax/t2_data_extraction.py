"""
T2 Financial Data Extraction Module
Extracts revenue, expenses, and balance sheet data for T2 return generation.
"""

import sys
from datetime import date
from decimal import Decimal

import psycopg2


class T2DataExtractor:
    """Extracts financial data from ALMS database for T2 returns."""
    
    def __init__(self, connection_params: dict):
        """Initialize with database connection parameters."""
        self.conn_params = connection_params
    
    def get_connection(self):
        """Create database connection."""
        return psycopg2.connect(**self.conn_params)
    
    def extract_revenue_data(self, tax_year: int) -> dict:
        """
        Extract all revenue for the tax year.
        
        Returns:
            Dict with revenue breakdown by source
        """
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            # Charter revenue (main business revenue)
            cur.execute("""
                SELECT 
                    COUNT(*) as charter_count,
                    COALESCE(SUM(total_amount_due), 0) as charter_revenue
                FROM charters
                WHERE EXTRACT(YEAR FROM charter_date) = %s
                AND status NOT IN ('cancelled', 'no-show')
            """, (tax_year,))
            
            charter_data = cur.fetchone()
            
            # Calculate GST (5% of total, tax-inclusive)
            if charter_data and len(charter_data) >= 2:
                charter_revenue = charter_data[1] if charter_data[1] is not None else Decimal('0')
                charter_gst = charter_revenue * Decimal('0.05') / Decimal('1.05')
                charter_count = charter_data[0]
            else:
                charter_revenue = Decimal('0')
                charter_gst = Decimal('0')
                charter_count = 0
            
            # Other income from receipts
            # Note: Skip this query for now, as most income comes from charters
            # We can add other income sources later if needed
            other_income = []
            
            # Banking credits (may include deposits, refunds, etc.)
            cur.execute("""
                SELECT 
                    COALESCE(SUM(credit_amount), 0) as total_credits,
                    COUNT(*) as credit_count
                FROM banking_transactions
                WHERE EXTRACT(YEAR FROM transaction_date) = %s
                AND credit_amount > 0
                AND receipt_id IS NULL  -- Not already matched to a receipt
            """, (tax_year,))
            
            banking_credits = cur.fetchone()
            
            return {
                'charter_revenue': {
                    'count': charter_count,
                    'amount': charter_revenue,
                    'gst': charter_gst
                },
                'other_income': [
                    {
                        'category': row[0],
                        'count': row[1],
                        'amount': row[2]
                    }
                    for row in other_income
                ],
                'banking_credits': {
                    'count': banking_credits[1],
                    'amount': banking_credits[0]
                },
                'total_revenue': charter_revenue + sum(row[2] for row in other_income)
            }
            
        finally:
            cur.close()
            conn.close()
    
    def extract_expense_data(self, tax_year: int) -> dict:
        """
        Extract all expenses for the tax year grouped by GL account.
        
        Returns:
            Dict with expense breakdown by GL code and category
        """
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            # Expenses by GL account code
            cur.execute("""
                SELECT 
                    COALESCE(r.gl_account_code, 'UNASSIGNED') as gl_code,
                    COALESCE(coa.account_name, 'Unassigned') as account_name,
                    COALESCE(coa.account_type, 'expense') as account_type,
                    r.category,
                    COUNT(*) as transaction_count,
                    COALESCE(SUM(r.gross_amount), 0) as total_amount,
                    COALESCE(SUM(r.gst_amount), 0) as total_gst
                FROM receipts r
                LEFT JOIN chart_of_accounts coa ON r.gl_account_code = coa.account_code
                WHERE EXTRACT(YEAR FROM r.receipt_date) = %s
                AND r.category NOT LIKE '%%Income%%'
                AND r.category != 'revenue'
                GROUP BY r.gl_account_code, coa.account_name, coa.account_type, r.category
                ORDER BY total_amount DESC
            """, (tax_year,))
            
            expense_details = cur.fetchall()
            
            # Summary by account type
            cur.execute("""
                SELECT 
                    COALESCE(coa.account_type, 'unassigned') as account_type,
                    COUNT(*) as transaction_count,
                    COALESCE(SUM(r.gross_amount), 0) as total_amount
                FROM receipts r
                LEFT JOIN chart_of_accounts coa ON r.gl_account_code = coa.account_code
                WHERE EXTRACT(YEAR FROM r.receipt_date) = %s
                AND r.category NOT LIKE '%%Income%%'
                AND r.category != 'revenue'
                GROUP BY coa.account_type
                ORDER BY total_amount DESC
            """, (tax_year,))
            
            expense_summary = cur.fetchall()
            
            # Calculate total expenses
            total_expenses = sum(row[6] for row in expense_details)
            total_gst_paid = sum(row[6] for row in expense_details)
            
            return {
                'by_gl_account': [
                    {
                        'gl_code': row[0],
                        'account_name': row[1],
                        'account_type': row[2],
                        'category': row[3],
                        'count': row[4],
                        'amount': row[5],
                        'gst': row[6]
                    }
                    for row in expense_details
                ],
                'by_account_type': [
                    {
                        'account_type': row[0],
                        'count': row[1],
                        'amount': row[2]
                    }
                    for row in expense_summary
                ],
                'total_expenses': total_expenses,
                'total_gst_paid': total_gst_paid
            }
            
        finally:
            cur.close()
            conn.close()
    
    def extract_balance_sheet_data(self, fiscal_year_end: date) -> dict:
        """
        Extract balance sheet data as of fiscal year end.
        
        For Schedule 100 - Balance Sheet Information
        """
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            # ASSETS
            # Cash (from banking transactions)
            cur.execute("""
                SELECT COALESCE(SUM(
                    COALESCE(credit_amount, 0) - COALESCE(debit_amount, 0)
                ), 0) as cash_balance
                FROM banking_transactions
                WHERE transaction_date <= %s
            """, (fiscal_year_end,))
            
            cash = cur.fetchone()[0]
            
            # Accounts Receivable (unpaid charters)
            cur.execute("""
                SELECT COALESCE(SUM(
                    total_amount_due - COALESCE(paid_amount, 0)
                ), 0) as ar_balance
                FROM charters
                WHERE charter_date <= %s
                AND status NOT IN ('cancelled', 'no-show')
                AND (paid_amount IS NULL OR paid_amount < total_amount_due)
            """, (fiscal_year_end,))
            
            accounts_receivable = cur.fetchone()[0]
            
            # Total Assets (simplified)
            total_assets = cash + accounts_receivable
            
            # LIABILITIES
            # Accounts Payable (estimate from recent unpaid expenses)
            cur.execute("""
                SELECT COALESCE(SUM(gross_amount), 0) as ap_estimate
                FROM receipts
                WHERE receipt_date <= %s
                AND receipt_date > %s - INTERVAL '30 days'
                AND banking_transaction_id IS NULL  -- Not yet paid
            """, (fiscal_year_end, fiscal_year_end))
            
            accounts_payable = cur.fetchone()[0]
            
            # Total Liabilities (simplified)
            total_liabilities = accounts_payable
            
            # EQUITY
            retained_earnings = total_assets - total_liabilities
            
            return {
                'assets': {
                    'cash': cash,
                    'accounts_receivable': accounts_receivable,
                    'total_assets': total_assets
                },
                'liabilities': {
                    'accounts_payable': accounts_payable,
                    'total_liabilities': total_liabilities
                },
                'equity': {
                    'retained_earnings': retained_earnings
                }
            }
            
        finally:
            cur.close()
            conn.close()
    
    def calculate_net_income(self, tax_year: int) -> dict:
        """
        Calculate net income for the year.
        
        Returns:
            Dict with revenue, expenses, and net income
        """
        revenue_data = self.extract_revenue_data(tax_year)
        expense_data = self.extract_expense_data(tax_year)
        
        total_revenue = revenue_data['total_revenue']
        total_expenses = expense_data['total_expenses']
        net_income = total_revenue - total_expenses
        
        return {
            'tax_year': tax_year,
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'net_income': net_income,
            'profit_margin': (net_income / total_revenue * 100) if total_revenue > 0 else 0
        }
    
    def get_tax_rates(self, tax_year: int) -> dict | None:
        """Get corporate tax rates for the given year."""
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT 
                    federal_small_business_rate,
                    federal_general_rate,
                    alberta_small_business_rate,
                    alberta_general_rate,
                    small_business_limit,
                    gst_rate
                FROM corporate_tax_rates
                WHERE tax_year = %s
            """, (tax_year,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            return {
                'federal_sbd': row[0],
                'federal_general': row[1],
                'alberta_sbd': row[2],
                'alberta_general': row[3],
                'small_business_limit': row[4],
                'gst_rate': row[5],
                'combined_sbd': row[0] + row[2],
                'combined_general': row[1] + row[3]
            }
            
        finally:
            cur.close()
            conn.close()
    
    def extract_complete_financial_package(self, tax_year: int, fiscal_year_end: date) -> dict:
        """
        Extract complete financial data package for T2 return generation.
        
        Args:
            tax_year: The tax year (e.g., 2023)
            fiscal_year_end: The fiscal year end date (e.g., 2023-12-31)
        
        Returns:
            Complete financial data package
        """
        print(f"\nExtracting financial data for tax year {tax_year}...")
        print("=" * 70)
        
        # Get all components
        revenue = self.extract_revenue_data(tax_year)
        expenses = self.extract_expense_data(tax_year)
        balance_sheet = self.extract_balance_sheet_data(fiscal_year_end)
        net_income = self.calculate_net_income(tax_year)
        tax_rates = self.get_tax_rates(tax_year)
        
        package = {
            'tax_year': tax_year,
            'fiscal_year_end': fiscal_year_end,
            'revenue': revenue,
            'expenses': expenses,
            'balance_sheet': balance_sheet,
            'net_income': net_income,
            'tax_rates': tax_rates
        }
        
        print(f"✓ Revenue data extracted: ${revenue['total_revenue']:,.2f}")
        print(f"✓ Expense data extracted: ${expenses['total_expenses']:,.2f}")
        print(f"✓ Net income calculated: ${net_income['net_income']:,.2f}")
        print(f"✓ Balance sheet as of {fiscal_year_end}")
        print(f"✓ Tax rates for {tax_year} loaded")
        
        return package


def main():
    """Test the data extraction."""
    from datetime import date
    
    # Database connection
    conn_params = {
        'dbname': 'almsdata',
        'user': 'postgres',
        'password': 'ArrowLimousine',
        'host': 'localhost'
    }
    
    extractor = T2DataExtractor(conn_params)
    
    # Test with 2023 (most recent complete year with good data)
    test_year = 2023
    fiscal_end = date(2023, 12, 31)
    
    print(f"\n{'='*70}")
    print(f"T2 FINANCIAL DATA EXTRACTION TEST - {test_year}")
    print(f"{'='*70}")
    
    try:
        # Extract complete package
        package = extractor.extract_complete_financial_package(test_year, fiscal_end)
        
        # Display summary
        print(f"\n{'='*70}")
        print("FINANCIAL SUMMARY")
        print(f"{'='*70}")
        
        print("\nREVENUE:")
        print(f"  Charter Revenue:        ${package['revenue']['charter_revenue']['amount']:>15,.2f}")
        print(f"  Charter Count:          {package['revenue']['charter_revenue']['count']:>15,}")
        print(f"  Other Income:           ${sum(i['amount'] for i in package['revenue']['other_income']):>15,.2f}")
        print(f"  {'─'*45}")
        print(f"  TOTAL REVENUE:          ${package['revenue']['total_revenue']:>15,.2f}")
        
        print("\nEXPENSES:")
        print(f"  Total Expenses:         ${package['expenses']['total_expenses']:>15,.2f}")
        print(f"  GST Paid:               ${package['expenses']['total_gst_paid']:>15,.2f}")
        
        print("\nNET INCOME:")
        print(f"  Net Income (Loss):      ${package['net_income']['net_income']:>15,.2f}")
        print(f"  Profit Margin:          {package['net_income']['profit_margin']:>15.1f}%")
        
        print(f"\nBALANCE SHEET (as of {fiscal_end}):")
        print(f"  Cash:                   ${package['balance_sheet']['assets']['cash']:>15,.2f}")
        print(f"  Accounts Receivable:    ${package['balance_sheet']['assets']['accounts_receivable']:>15,.2f}")
        print(f"  Total Assets:           ${package['balance_sheet']['assets']['total_assets']:>15,.2f}")
        print(f"  Accounts Payable:       ${package['balance_sheet']['liabilities']['accounts_payable']:>15,.2f}")
        print(f"  Retained Earnings:      ${package['balance_sheet']['equity']['retained_earnings']:>15,.2f}")
        
        if package['tax_rates']:
            print(f"\nTAX RATES ({test_year}):")
            print(f"  Combined SBD Rate:      {package['tax_rates']['combined_sbd']*100:>15.1f}%")
            print(f"  Combined General Rate:  {package['tax_rates']['combined_general']*100:>15.1f}%")
            print(f"  Small Business Limit:   ${package['tax_rates']['small_business_limit']:>15,.2f}")
            print(f"  GST Rate:               {package['tax_rates']['gst_rate']*100:>15.1f}%")
        
        print(f"\n{'='*70}")
        print("✓ DATA EXTRACTION SUCCESSFUL")
        print(f"{'='*70}\n")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
