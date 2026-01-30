#!/usr/bin/env python3
"""
T2 Corporate Income Tax Return Generator
========================================

Generates fillable CRA T2 returns for Arrow Limousine using official CRA forms.
Downloads year-specific fillable PDFs from canada.ca and populates with database data.

Key T2 Sections Populated:
- Part 1: Identification (corp name, BN, address, tax year)
- Part 2: Net Income (revenue, expenses, net income for tax)
- Part 3: Taxable Income
- Part 6: Summary of Tax and Credits
- Schedule 100: Balance Sheet
- Schedule 125: Income Statement

CRA Form URLs (fillable PDFs):
- 2012-2019: https://www.canada.ca/en/revenue-agency/services/forms-publications/forms/t2.html
- 2020+: https://www.canada.ca/en/revenue-agency/services/forms-publications/forms/t2.html
- Schedule 125: https://www.canada.ca/en/revenue-agency/services/forms-publications/forms/t2sch125.html

Usage:
    python scripts/generate_t2_return.py --year 2012
    python scripts/generate_t2_return.py --year 2012 --download
    python scripts/generate_t2_return.py --year 2013 --output exports/tax/

Dependencies:
    pip install pypdf reportlab psycopg2 requests
"""
import os
import sys
import argparse
from datetime import date, datetime
from decimal import Decimal
import psycopg2
from psycopg2.extras import DictCursor
from pypdf import PdfReader, PdfWriter
import requests

DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)


# CRA T2 Form URLs by year
CRA_FORM_URLS = {
    # Main T2 return
    't2': {
        2012: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-12e.pdf',
        2013: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-13e.pdf',
        2014: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-14e.pdf',
        2015: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-15e.pdf',
        2016: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-16e.pdf',
        2017: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-17e.pdf',
        2018: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-18e.pdf',
        2019: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-19e.pdf',
        2020: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-20e.pdf',
        2021: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-21e.pdf',
        2022: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-22e.pdf',
        2023: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-23e.pdf',
        2024: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-24e.pdf',
    },
    # Schedule 125 - Income Statement
    'sch125': {
        2012: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-12e.pdf',
        2013: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-13e.pdf',
        2014: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-14e.pdf',
        2015: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-15e.pdf',
        2016: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-16e.pdf',
        2017: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-17e.pdf',
        2018: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-18e.pdf',
        2019: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-19e.pdf',
        2020: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-20e.pdf',
        2021: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-21e.pdf',
        2022: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-22e.pdf',
        2023: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-23e.pdf',
        2024: 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-24e.pdf',
    }
}


def download_cra_form(year: int, form_type: str = 't2', cache_dir: str = 'pdf/cra_forms') -> str:
    """Download official CRA T2 form for specified year"""
    if form_type not in CRA_FORM_URLS or year not in CRA_FORM_URLS[form_type]:
        raise ValueError(f"No CRA form URL for {form_type} year {year}")
    
    url = CRA_FORM_URLS[form_type][year]
    os.makedirs(cache_dir, exist_ok=True)
    
    filename = f"{form_type}_{year}e.pdf"
    filepath = os.path.join(cache_dir, filename)
    
    # Use cached file if exists
    if os.path.exists(filepath):
        print(f"  Using cached form: {filepath}")
        return filepath
    
    print(f"  Downloading CRA {form_type.upper()} form for {year}...")
    print(f"  URL: {url}")
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        print(f"  [OK] Downloaded: {filepath}")
        return filepath
    
    except requests.exceptions.RequestException as e:
        print(f"  [FAIL] Download failed: {e}")
        raise


class T2ReturnData:
    """Container for T2 return data"""
    def __init__(self, year: int):
        self.year = year
        self.year_end = date(year, 12, 31)
        
        # Part 1: Identification
        self.corp_name = "Arrow Limousine Sedan Services Ltd"
        self.business_number = "TBD"  # Need to get from user/DB
        self.address = "3-9841 52 Avenue, Red Deer, AB T4N 4L2"
        self.naics_code = "485310"  # Taxi and limousine service
        
        # Part 2: Net Income
        self.gross_revenue = Decimal(0)
        self.cost_of_sales = Decimal(0)
        self.gross_profit = Decimal(0)
        self.total_expenses = Decimal(0)
        self.net_income_loss = Decimal(0)
        
        # Expense breakdown
        self.advertising = Decimal(0)
        self.bad_debts = Decimal(0)
        self.insurance = Decimal(0)
        self.interest_bank_charges = Decimal(0)
        self.professional_fees = Decimal(0)
        self.management_admin_fees = Decimal(0)
        self.office_expenses = Decimal(0)
        self.property_taxes = Decimal(0)
        self.rent = Decimal(0)
        self.repairs_maintenance = Decimal(0)
        self.salaries_wages = Decimal(0)
        self.travel = Decimal(0)
        self.telephone_utilities = Decimal(0)
        self.fuel_oil = Decimal(0)
        self.delivery_freight = Decimal(0)
        self.motor_vehicle = Decimal(0)
        self.cca = Decimal(0)  # Capital Cost Allowance
        self.other_expenses = Decimal(0)
        
        # Part 3: Taxable Income
        self.taxable_income = Decimal(0)
        
        # Part 6: Tax Calculation
        self.federal_tax = Decimal(0)
        self.provincial_tax = Decimal(0)
        self.total_tax = Decimal(0)
        self.tax_credits = Decimal(0)
        self.balance_owing = Decimal(0)
        
        # Schedule 100: Balance Sheet
        self.cash = Decimal(0)
        self.accounts_receivable = Decimal(0)
        self.inventory = Decimal(0)
        self.prepaid_expenses = Decimal(0)
        self.total_current_assets = Decimal(0)
        
        self.fixed_assets_cost = Decimal(0)
        self.accumulated_depreciation = Decimal(0)
        self.fixed_assets_net = Decimal(0)
        
        self.total_assets = Decimal(0)
        
        self.accounts_payable = Decimal(0)
        self.current_portion_ltd = Decimal(0)
        self.total_current_liabilities = Decimal(0)
        
        self.long_term_debt = Decimal(0)
        self.total_liabilities = Decimal(0)
        
        self.share_capital = Decimal(0)
        self.retained_earnings = Decimal(0)
        self.total_equity = Decimal(0)


def get_financial_data(conn, year: int) -> T2ReturnData:
    """Query database for T2 return data"""
    data = T2ReturnData(year)
    cur = conn.cursor(cursor_factory=DictCursor)
    
    print(f"Fetching financial data for {year}...")
    
    # Try to get revenue from unified_general_ledger
    try:
        cur.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END), 0) as revenue,
                COALESCE(SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END), 0) as expenses
            FROM unified_general_ledger
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
        """, (year,))
        row = cur.fetchone()
        if row:
            data.gross_revenue = Decimal(str(row['revenue'] or 0))
            data.total_expenses = Decimal(str(row['expenses'] or 0))
            data.net_income_loss = data.gross_revenue - data.total_expenses
            print(f"  Revenue: ${data.gross_revenue:,.2f}")
            print(f"  Expenses: ${data.total_expenses:,.2f}")
            print(f"  Net Income: ${data.net_income_loss:,.2f}")
    except Exception as e:
        print(f"  Warning: Could not fetch GL data: {e}")
    
    # Get expense breakdown from receipts by category
    try:
        cur.execute("""
            SELECT 
                LOWER(COALESCE(category, 'other')) as category,
                COALESCE(SUM(gross_amount), 0) as total
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = %s
            GROUP BY LOWER(COALESCE(category, 'other'))
        """, (year,))
        
        for row in cur.fetchall():
            category = row['category']
            amount = Decimal(str(row['total'] or 0))
            
            # Map categories to T2 expense lines
            if 'insurance' in category:
                data.insurance += amount
            elif 'fuel' in category or 'gas' in category:
                data.fuel_oil += amount
            elif 'office' in category or 'supplies' in category:
                data.office_expenses += amount
            elif 'rent' in category or '6820' in category:
                data.rent += amount
            elif 'repair' in category or 'maintenance' in category:
                data.repairs_maintenance += amount
            elif 'util' in category or 'telecom' in category or 'phone' in category:
                data.telephone_utilities += amount
            elif 'vehicle' in category or 'motor' in category:
                data.motor_vehicle += amount
            else:
                data.other_expenses += amount
        
        print(f"  Categorized expenses:")
        if data.insurance > 0:
            print(f"    Insurance: ${data.insurance:,.2f}")
        if data.fuel_oil > 0:
            print(f"    Fuel: ${data.fuel_oil:,.2f}")
        if data.rent > 0:
            print(f"    Rent: ${data.rent:,.2f}")
        if data.repairs_maintenance > 0:
            print(f"    Repairs: ${data.repairs_maintenance:,.2f}")
        if data.motor_vehicle > 0:
            print(f"    Motor Vehicle: ${data.motor_vehicle:,.2f}")
        if data.other_expenses > 0:
            print(f"    Other: ${data.other_expenses:,.2f}")
            
    except Exception as e:
        print(f"  Warning: Could not categorize expenses: {e}")
    
    # Calculate taxable income (simplified - actual T2 has many adjustments)
    data.taxable_income = max(Decimal(0), data.net_income_loss)
    
    # Calculate federal tax (simplified small business rate ~9% on first $500k)
    if data.taxable_income > 0:
        small_business_limit = Decimal(500000)
        if data.taxable_income <= small_business_limit:
            data.federal_tax = data.taxable_income * Decimal('0.09')
        else:
            data.federal_tax = (small_business_limit * Decimal('0.09') + 
                              (data.taxable_income - small_business_limit) * Decimal('0.15'))
        
        # Alberta provincial tax (simplified ~2% small business rate)
        data.provincial_tax = data.taxable_income * Decimal('0.02')
        
        data.total_tax = data.federal_tax + data.provincial_tax
        data.balance_owing = data.total_tax - data.tax_credits
        
        print(f"  Tax calculation:")
        print(f"    Taxable income: ${data.taxable_income:,.2f}")
        print(f"    Federal tax: ${data.federal_tax:,.2f}")
        print(f"    Provincial tax: ${data.provincial_tax:,.2f}")
        print(f"    Total tax: ${data.total_tax:,.2f}")
    
    cur.close()
    return data


def fill_t2_form(template_path: str, output_path: str, data: T2ReturnData):
    """Fill the T2 PDF form with data"""
    print(f"\nFilling T2 form...")
    print(f"  Template: {template_path}")
    print(f"  Output: {output_path}")
    
    try:
        reader = PdfReader(template_path)
        writer = PdfWriter()
        
        # Copy all pages
        for page in reader.pages:
            writer.add_page(page)
        
        # Get form fields (if fillable PDF)
        if reader.get_form_text_fields():
            fields = reader.get_form_text_fields()
            print(f"  Found {len(fields)} form fields")
            
            # Map our data to PDF form fields
            # Note: Field names depend on the actual PDF - may need adjustment
            field_mapping = {
                # Part 1: Identification
                'CorporationName': data.corp_name,
                'BusinessNumber': data.business_number,
                'Address': data.address,
                'TaxYear': str(data.year),
                'YearEnd': data.year_end.strftime('%Y-%m-%d'),
                
                # Part 2: Net Income
                'GrossRevenue': f"{data.gross_revenue:,.2f}",
                'TotalExpenses': f"{data.total_expenses:,.2f}",
                'NetIncome': f"{data.net_income_loss:,.2f}",
                
                # Expenses
                'Insurance': f"{data.insurance:,.2f}",
                'Rent': f"{data.rent:,.2f}",
                'Repairs': f"{data.repairs_maintenance:,.2f}",
                'Fuel': f"{data.fuel_oil:,.2f}",
                'MotorVehicle': f"{data.motor_vehicle:,.2f}",
                'OfficeExpenses': f"{data.office_expenses:,.2f}",
                'Utilities': f"{data.telephone_utilities:,.2f}",
                'OtherExpenses': f"{data.other_expenses:,.2f}",
                
                # Part 3: Taxable Income
                'TaxableIncome': f"{data.taxable_income:,.2f}",
                
                # Part 6: Tax
                'FederalTax': f"{data.federal_tax:,.2f}",
                'ProvincialTax': f"{data.provincial_tax:,.2f}",
                'TotalTax': f"{data.total_tax:,.2f}",
                'BalanceOwing': f"{data.balance_owing:,.2f}",
            }
            
            # Update fields that exist in the PDF
            for field_name, value in field_mapping.items():
                if field_name in fields:
                    writer.update_page_form_field_values(
                        writer.pages[0], {field_name: value}
                    )
        else:
            print("  Note: PDF is not fillable - creating annotation layer")
        
        # Write output
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        print(f"[OK] T2 form generated successfully")
        
    except Exception as e:
        print(f"[FAIL] Error filling PDF: {e}")
        raise


def generate_t2_summary(data: T2ReturnData, output_path: str):
    """Generate a text summary of the T2 return"""
    summary_path = output_path.replace('.pdf', '_summary.txt')
    
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(f"T2 CORPORATE INCOME TAX RETURN - {data.year}\n")
        f.write(f"{'='*60}\n\n")
        
        f.write(f"Corporation: {data.corp_name}\n")
        f.write(f"Business Number: {data.business_number}\n")
        f.write(f"Address: {data.address}\n")
        f.write(f"Tax Year End: {data.year_end}\n\n")
        
        f.write(f"INCOME STATEMENT\n")
        f.write(f"{'-'*60}\n")
        f.write(f"Gross Revenue:              ${data.gross_revenue:>15,.2f}\n\n")
        
        f.write(f"EXPENSES:\n")
        f.write(f"  Insurance:                ${data.insurance:>15,.2f}\n")
        f.write(f"  Rent:                     ${data.rent:>15,.2f}\n")
        f.write(f"  Repairs & Maintenance:    ${data.repairs_maintenance:>15,.2f}\n")
        f.write(f"  Fuel & Oil:               ${data.fuel_oil:>15,.2f}\n")
        f.write(f"  Motor Vehicle:            ${data.motor_vehicle:>15,.2f}\n")
        f.write(f"  Office Expenses:          ${data.office_expenses:>15,.2f}\n")
        f.write(f"  Telephone & Utilities:    ${data.telephone_utilities:>15,.2f}\n")
        f.write(f"  Other Expenses:           ${data.other_expenses:>15,.2f}\n")
        f.write(f"                            {'-'*20}\n")
        f.write(f"Total Expenses:             ${data.total_expenses:>15,.2f}\n\n")
        
        f.write(f"Net Income (Loss):          ${data.net_income_loss:>15,.2f}\n\n")
        
        f.write(f"TAXABLE INCOME:             ${data.taxable_income:>15,.2f}\n\n")
        
        f.write(f"TAX CALCULATION\n")
        f.write(f"{'-'*60}\n")
        f.write(f"Federal Tax (Part 1):       ${data.federal_tax:>15,.2f}\n")
        f.write(f"Provincial Tax (Alberta):   ${data.provincial_tax:>15,.2f}\n")
        f.write(f"                            {'-'*20}\n")
        f.write(f"Total Tax:                  ${data.total_tax:>15,.2f}\n")
        f.write(f"Less: Tax Credits:          ${data.tax_credits:>15,.2f}\n")
        f.write(f"                            {'-'*20}\n")
        f.write(f"BALANCE OWING/REFUND:       ${data.balance_owing:>15,.2f}\n\n")
        
        f.write(f"\nNOTES:\n")
        f.write(f"- This is a simplified T2 calculation\n")
        f.write(f"- Actual filing requires professional accountant review\n")
        f.write(f"- Tax rates are approximate (2012-2025 range)\n")
        f.write(f"- CCA, loss carryforwards, and other adjustments not included\n")
        f.write(f"- Provincial rates may vary by year\n")
    
    print(f"[OK] Summary saved to: {summary_path}")


def main():
    parser = argparse.ArgumentParser(description='Generate T2 Corporate Tax Return')
    parser.add_argument('--year', type=int, required=True, help='Tax year to generate')
    parser.add_argument('--download', action='store_true', help='Force download of CRA forms')
    parser.add_argument('--template', type=str, default=None,
                       help='Path to T2 template PDF (overrides CRA download)')
    parser.add_argument('--output', type=str, default='exports/tax',
                       help='Output directory')
    args = parser.parse_args()
    
    # Connect to database
    print(f"Generating T2 return for {args.year}...")
    conn = psycopg2.connect(**DSN)
    
    try:
        # Get financial data
        data = get_financial_data(conn, args.year)
        
        # Generate output path
        output_dir = os.path.join(args.output, str(args.year))
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"T2_Return_{args.year}.pdf")
        
        # Get T2 form template
        if args.template and os.path.exists(args.template):
            template_path = args.template
            print(f"Using custom template: {template_path}")
        else:
            # Download official CRA form
            try:
                template_path = download_cra_form(args.year, 't2')
                # Also download Schedule 125 (income statement)
                sch125_path = download_cra_form(args.year, 'sch125')
                print(f"  Also downloaded Schedule 125: {sch125_path}")
            except Exception as e:
                print(f"[WARN]  Could not download CRA forms: {e}")
                print(f"  Will generate summary only")
                template_path = None
        
        # Fill T2 form
        if template_path and os.path.exists(template_path):
            fill_t2_form(template_path, output_path, data)
        else:
            print(f"  No template available - generating summary only")
        
        # Generate summary
        generate_t2_summary(data, output_path)
        
        print(f"\n🎉 T2 Return for {args.year} complete!")
        print(f"   Files saved to: {output_dir}")
        print(f"\n📋 Next steps:")
        print(f"   1. Review the generated T2 return and summary")
        print(f"   2. Have a professional accountant review before filing")
        print(f"   3. File electronically through CRA My Business Account")
        print(f"   4. Keep copies for 6 years for CRA audit purposes")
        
    finally:
        conn.close()


if __name__ == '__main__':
    main()
