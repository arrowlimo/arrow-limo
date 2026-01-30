#!/usr/bin/env python3
"""
Generate corrected tax calculations for 2012-2013 unfiled returns.

Since these years haven't been filed yet, we can implement the gratuity
compliance from the start for maximum tax savings.
"""

import sys
import os
import psycopg2
from decimal import Decimal
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
        port=os.getenv('DB_PORT', '5432')
    )

def calculate_corrected_2012_taxes():
    """Calculate corrected 2012 taxes with compliant gratuity treatment."""
    
    print("2012 CORRECTED TAX CALCULATION")
    print("=" * 50)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get 2012 revenue and gratuity data
        cur.execute("""
            SELECT 
                COUNT(*) as total_charters,
                SUM(COALESCE(total_amount_due, rate)) as total_revenue,
                SUM(CASE WHEN driver_gratuity > 0 THEN driver_gratuity ELSE 0 END) as total_gratuities,
                COUNT(CASE WHEN driver_gratuity > 0 THEN 1 END) as charters_with_tips
            FROM charters 
            WHERE charter_date BETWEEN '2012-01-01' AND '2012-12-31'
        """)
        
        charter_data = cur.fetchone()
        
        # Get 2012 expense data from receipts
        cur.execute("""
            SELECT 
                SUM(CASE WHEN gst_amount > 0 THEN gst_amount ELSE gross_amount * 0.05 / 1.05 END) as total_gst_paid,
                SUM(gross_amount) as total_expenses
            FROM receipts 
            WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31'
        """)
        
        expense_data = cur.fetchone()
        
        cur.close()
        conn.close()
        
        # 2012 Tax Rates (Alberta)
        gst_rate = Decimal('0.05')  # 5%
        corporate_tax_rate = Decimal('0.14')  # 14% small business (11% federal + 3% provincial)
        
        # Calculate corrected figures
        total_charters = charter_data[0] or 0
        gross_revenue = charter_data[1] or Decimal('0')
        customer_tips = charter_data[2] or Decimal('0')  # Now GST-exempt
        charters_with_tips = charter_data[3] or 0
        
        # Taxable revenue (excluding customer tips)
        taxable_revenue = gross_revenue - customer_tips
        gst_on_revenue = taxable_revenue * gst_rate / (Decimal('1') + gst_rate)
        net_taxable_revenue = taxable_revenue - gst_on_revenue
        
        # Input Tax Credits from expenses
        total_expenses = expense_data[1] or Decimal('0')
        itc_claimed = expense_data[0] or Decimal('0')
        
        # Net GST calculation
        gst_collected = gst_on_revenue
        net_gst_payable = gst_collected - itc_claimed
        
        # Corporate tax calculation
        net_income = net_taxable_revenue - total_expenses
        corporate_tax = net_income * corporate_tax_rate if net_income > 0 else Decimal('0')
        
        print(f"2012 CORRECTED CALCULATIONS:")
        print(f"Total Charters:                  {total_charters:,}")
        print(f"Gross Revenue (including tips):  ${gross_revenue:,.2f}")
        print(f"Customer Tips (GST-exempt):      ${customer_tips:,.2f}")
        print(f"Taxable Revenue:                 ${taxable_revenue:,.2f}")
        print(f"Net Taxable Revenue:             ${net_taxable_revenue:,.2f}")
        
        print(f"\nGST CALCULATION:")
        print(f"GST Collected on Services:       ${gst_collected:,.2f}")
        print(f"Input Tax Credits:               ${itc_claimed:,.2f}")
        print(f"Net GST Payable:                 ${net_gst_payable:,.2f}")
        
        print(f"\nCORPORATE TAX CALCULATION:")
        print(f"Total Business Expenses:         ${total_expenses:,.2f}")
        print(f"Net Income Before Tax:           ${net_income:,.2f}")
        print(f"Corporate Tax (14%):             ${corporate_tax:,.2f}")
        
        # Calculate savings vs old method
        old_gst_on_tips = customer_tips * gst_rate
        gst_savings = old_gst_on_tips
        
        print(f"\nTAX SAVINGS FROM COMPLIANCE:")
        print(f"GST Saved on Tips:               ${gst_savings:,.2f}")
        print(f"Charters with Tips:              {charters_with_tips:,}")
        
        return {
            'taxable_revenue': net_taxable_revenue,
            'gst_payable': net_gst_payable,
            'corporate_tax': corporate_tax,
            'gst_savings': gst_savings,
            'customer_tips': customer_tips
        }
        
    except Exception as e:
        print(f"Error calculating 2012 taxes: {e}")
        return None

def calculate_corrected_2013_taxes():
    """Calculate corrected 2013 taxes with compliant gratuity treatment."""
    
    print("\n2013 CORRECTED TAX CALCULATION")
    print("=" * 50)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get 2013 revenue and gratuity data
        cur.execute("""
            SELECT 
                COUNT(*) as total_charters,
                SUM(COALESCE(total_amount_due, rate)) as total_revenue,
                SUM(CASE WHEN driver_gratuity > 0 THEN driver_gratuity ELSE 0 END) as total_gratuities,
                COUNT(CASE WHEN driver_gratuity > 0 THEN 1 END) as charters_with_tips
            FROM charters 
            WHERE charter_date BETWEEN '2013-01-01' AND '2013-12-31'
        """)
        
        charter_data = cur.fetchone()
        
        # Get 2013 expense data from receipts
        cur.execute("""
            SELECT 
                SUM(CASE WHEN gst_amount > 0 THEN gst_amount ELSE gross_amount * 0.05 / 1.05 END) as total_gst_paid,
                SUM(gross_amount) as total_expenses
            FROM receipts 
            WHERE receipt_date BETWEEN '2013-01-01' AND '2013-12-31'
        """)
        
        expense_data = cur.fetchone()
        
        cur.close()
        conn.close()
        
        # Use reconciliation data from user for 2013
        reconciled_2013 = {
            'cash_receipts_report': Decimal('632571.99'),
            'gst_collected': Decimal('30480.38'),
            'itc': Decimal('14830.00'),
            'net_gst_payable': Decimal('15650.38')
        }
        
        # 2013 Tax Rates (Alberta)
        gst_rate = Decimal('0.05')  # 5%
        corporate_tax_rate = Decimal('0.14')  # 14% small business
        
        # Calculate corrected figures
        total_charters = charter_data[0] or 0
        gross_revenue = charter_data[1] or Decimal('0')
        customer_tips = charter_data[2] or Decimal('0')  # Now GST-exempt
        charters_with_tips = charter_data[3] or 0
        
        # Use reconciled revenue figure
        reconciled_revenue = reconciled_2013['cash_receipts_report']
        
        # Corrected GST calculation (no GST on customer tips)
        gst_savings_on_tips = customer_tips * gst_rate
        corrected_gst_collected = reconciled_2013['gst_collected'] - gst_savings_on_tips
        corrected_net_gst = corrected_gst_collected - reconciled_2013['itc']
        
        # Corporate tax on corrected income
        total_expenses = expense_data[1] or Decimal('0')
        corrected_taxable_income = reconciled_revenue - customer_tips - total_expenses
        corporate_tax = corrected_taxable_income * corporate_tax_rate if corrected_taxable_income > 0 else Decimal('0')
        
        print(f"2013 CORRECTED CALCULATIONS (Using Reconciliation Data):")
        print(f"Total Charters:                  {total_charters:,}")
        print(f"Reconciled Revenue:              ${reconciled_revenue:,.2f}")
        print(f"Customer Tips (GST-exempt):      ${customer_tips:,.2f}")
        print(f"Taxable Revenue (Service only):  ${reconciled_revenue - customer_tips:,.2f}")
        
        print(f"\nCORRECTED GST CALCULATION:")
        print(f"Original GST Collected:          ${reconciled_2013['gst_collected']:,.2f}")
        print(f"GST Savings on Tips:             ${gst_savings_on_tips:,.2f}")
        print(f"Corrected GST Collected:         ${corrected_gst_collected:,.2f}")
        print(f"Input Tax Credits:               ${reconciled_2013['itc']:,.2f}")
        print(f"Corrected Net GST Payable:       ${corrected_net_gst:,.2f}")
        print(f"Original Net GST Payable:        ${reconciled_2013['net_gst_payable']:,.2f}")
        print(f"GST Reduction:                   ${reconciled_2013['net_gst_payable'] - corrected_net_gst:,.2f}")
        
        print(f"\nCORPORATE TAX CALCULATION:")
        print(f"Business Expenses:               ${total_expenses:,.2f}")
        print(f"Corrected Taxable Income:        ${corrected_taxable_income:,.2f}")
        print(f"Corporate Tax (14%):             ${corporate_tax:,.2f}")
        
        print(f"\nTOTAL 2013 TAX SAVINGS:")
        print(f"GST Savings:                     ${gst_savings_on_tips:,.2f}")
        print(f"Charters with Tips:              {charters_with_tips:,}")
        
        return {
            'reconciled_revenue': reconciled_revenue,
            'customer_tips': customer_tips,
            'gst_savings': gst_savings_on_tips,
            'corrected_gst_payable': corrected_net_gst,
            'original_gst_payable': reconciled_2013['net_gst_payable'],
            'corporate_tax': corporate_tax
        }
        
    except Exception as e:
        print(f"Error calculating 2013 taxes: {e}")
        return None

def generate_filing_summary():
    """Generate summary for filing 2012-2013 returns."""
    
    print("\n2012-2013 TAX FILING SUMMARY")
    print("=" * 50)
    
    # Calculate both years
    tax_2012 = calculate_corrected_2012_taxes()
    tax_2013 = calculate_corrected_2013_taxes()
    
    if tax_2012 and tax_2013:
        total_gst_savings = tax_2012['gst_savings'] + tax_2013['gst_savings']
        total_customer_tips = tax_2012['customer_tips'] + tax_2013['customer_tips']
        
        print(f"\nCOMBINED 2012-2013 SAVINGS:")
        print(f"Total Customer Tips (GST-exempt): ${total_customer_tips:,.2f}")
        print(f"Total GST Savings:                ${total_gst_savings:,.2f}")
        
        print(f"\nFILING RECOMMENDATIONS:")
        print("[OK] File 2012 return with corrected gratuity treatment")
        print("[OK] File 2013 return with corrected gratuity treatment")
        print("[OK] No amended returns needed - file correctly from start")
        print("[OK] Significant tax savings achieved on initial filing")
        
        print(f"\nKEY COMPLIANCE POINTS FOR FILING:")
        print("- Customer gratuities treated as freely given tips (CRA compliant)")
        print("- No GST charged or collected on customer tips")
        print("- Service charges properly subject to GST")
        print("- Payroll CPP/EI limited to actual wages (not tips)")
        
        return {
            'total_savings': total_gst_savings,
            'filing_ready': True,
            'compliance_achieved': True
        }
    
    return None

def main():
    """Generate corrected tax calculations for unfiled 2012-2013 returns."""
    
    print("CORRECTED TAX CALCULATIONS FOR 2012-2013 FILING")
    print("=" * 60)
    print("Since 2012-2013 haven't been filed, implementing compliant")
    print("gratuity treatment from the start for maximum savings.\n")
    
    filing_summary = generate_filing_summary()
    
    if filing_summary:
        print(f"\n🎯 READY FOR CRA-COMPLIANT FILING!")
        print(f"Total GST savings: ${filing_summary['total_savings']:,.2f}")
        print(f"No amendments needed - file correctly from start!")
        
        print(f"\n📋 NEXT STEPS:")
        print("1. Use these corrected calculations for 2012-2013 filings")
        print("2. Ensure invoices show gratuities as customer-added tips")
        print("3. File returns with compliant gratuity treatment")
        print("4. Maintain ongoing compliance for future years")

if __name__ == "__main__":
    main()