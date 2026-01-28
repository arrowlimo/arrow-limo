#!/usr/bin/env python3
"""
Arrow Limousine 2012 Tax Year Calculation - ACCURATE 2012 RATES
==============================================================

This script calculates the complete tax situation for Arrow Limousine
using the EXACT 2012 Canadian tax rates and thresholds.

2012 Tax Year Specifications:
- Federal Small Business Rate: 11%
- Alberta Small Business Rate: 3%
- Small Business Limit: $400,000
- GST Rate: 5% (Alberta)
- Federal General Corporate Rate: 15%
- Alberta General Corporate Rate: 10%

Author: AI Agent
Date: October 2025
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def get_2012_tax_rates():
    """Official 2012 Canadian corporate tax rates for Alberta."""
    return {
        # Corporate Income Tax Rates (2012)
        'federal_small_business': Decimal('0.11'),      # 11% federal small business deduction
        'alberta_small_business': Decimal('0.03'),      # 3% Alberta small business rate
        'combined_small_business': Decimal('0.14'),     # 14% combined small business rate
        
        'federal_general': Decimal('0.15'),             # 15% federal general corporate rate
        'alberta_general': Decimal('0.10'),             # 10% Alberta general corporate rate
        'combined_general': Decimal('0.25'),            # 25% combined general corporate rate
        
        # Thresholds and Limits (2012)
        'small_business_limit': Decimal('400000'),      # $400,000 annual small business limit
        'small_business_limit_monthly': Decimal('33333.33'),  # Monthly allocation
        
        # GST/HST Rates (2012)
        'gst_rate': Decimal('0.05'),                    # 5% GST (Alberta - no provincial sales tax)
        'gst_registration_threshold': Decimal('30000'), # $30,000 GST registration threshold
        'gst_quarterly_threshold': Decimal('3000'),     # $3,000 quarterly GST threshold
        
        # Employment Tax Rates (2012)
        'cpp_rate': Decimal('0.0495'),                  # 4.95% CPP (employee + employer combined)
        'ei_rate': Decimal('0.0238'),                   # 2.38% EI (employee + employer combined)
        'cpp_maximum': Decimal('2306.70'),              # Maximum annual CPP contribution
        'ei_maximum': Decimal('839.97'),                # Maximum annual EI premium
        'cpp_exemption': Decimal('3500'),               # Basic CPP exemption
        'ei_insurable_maximum': Decimal('45900'),       # Maximum EI insurable earnings
    }

def calculate_business_revenue_2012(conn):
    """Calculate total business revenue for 2012 using our documented records."""
    cur = conn.cursor()
    
    # Revenue from our banking classification project
    cur.execute("""
        SELECT SUM(gross_amount) as total_revenue,
               SUM(gst_amount) as gst_collected,
               SUM(net_amount) as net_revenue,
               COUNT(*) as revenue_transactions
        FROM receipts 
        WHERE EXTRACT(year FROM receipt_date) = 2012
          AND source_system = 'BANKING_REVENUE'
    """)
    
    banking_revenue = cur.fetchone()
    
    # Charter revenue (operational bookings)
    cur.execute("""
        SELECT SUM(COALESCE(total_amount_due, rate)) as charter_revenue,
               COUNT(*) as charter_count,
               SUM(CASE WHEN payment_status = 'paid' THEN COALESCE(paid_amount, total_amount_due, rate) ELSE 0 END) as paid_revenue
        FROM charters 
        WHERE EXTRACT(year FROM charter_date) = 2012
          AND status NOT IN ('cancelled', 'no-show')
    """)
    
    charter_data = cur.fetchone()
    
    # Square and credit card payments
    cur.execute("""
        SELECT SUM(amount) as card_revenue,
               COUNT(*) as card_transactions
        FROM payments 
        WHERE EXTRACT(year FROM payment_date) = 2012
          AND (payment_method ILIKE '%square%' OR payment_method ILIKE '%card%' OR payment_method ILIKE '%credit%')
    """)
    
    card_data = cur.fetchone()
    
    cur.close()
    
    return {
        'banking_gross': Decimal(str(banking_revenue[0] or 0)),
        'banking_gst': Decimal(str(banking_revenue[1] or 0)),
        'banking_net': Decimal(str(banking_revenue[2] or 0)),
        'banking_count': banking_revenue[3] or 0,
        
        'charter_revenue': Decimal(str(charter_data[0] or 0)),
        'charter_paid': Decimal(str(charter_data[2] or 0)),
        'charter_count': charter_data[1] or 0,
        
        'card_revenue': Decimal(str(card_data[0] or 0)),
        'card_count': card_data[1] or 0
    }

def calculate_business_expenses_2012(conn):
    """Calculate deductible business expenses for 2012."""
    cur = conn.cursor()
    
    # Vehicle and transportation expenses
    cur.execute("""
        SELECT SUM(gross_amount) as vehicle_total,
               SUM(gst_amount) as vehicle_gst,
               COUNT(*) as vehicle_count
        FROM receipts 
        WHERE EXTRACT(year FROM receipt_date) = 2012
          AND (source_system = 'BANKING_TRANSACTION' 
               OR vendor_name ILIKE '%woodridge%ford%'
               OR category ILIKE '%vehicle%'
               OR category ILIKE '%fuel%')
    """)
    
    vehicle_data = cur.fetchone()
    
    # Banking and financial expenses
    cur.execute("""
        SELECT SUM(gross_amount) as banking_total,
               COUNT(*) as banking_count
        FROM receipts 
        WHERE EXTRACT(year FROM receipt_date) = 2012
          AND source_system = 'banking_import'
    """)
    
    banking_expense_data = cur.fetchone()
    
    # Other business expenses from QuickBooks
    cur.execute("""
        SELECT SUM(gross_amount) as qb_expenses,
               SUM(gst_amount) as qb_gst,
               COUNT(*) as qb_count
        FROM receipts 
        WHERE EXTRACT(year FROM receipt_date) = 2012
          AND source_system = 'QuickBooks-2012-Import'
          AND (category ILIKE '%expense%' OR gross_amount < 0)
    """)
    
    qb_expense_data = cur.fetchone()
    
    cur.close()
    
    return {
        'vehicle_expenses': Decimal(str(vehicle_data[0] or 0)),
        'vehicle_gst_paid': Decimal(str(vehicle_data[1] or 0)),
        'vehicle_count': vehicle_data[2] or 0,
        
        'banking_expenses': Decimal(str(banking_expense_data[0] or 0)),
        'banking_count': banking_expense_data[1] or 0,
        
        'qb_expenses': abs(Decimal(str(qb_expense_data[0] or 0))),  # Expenses are negative in QB
        'qb_gst_paid': Decimal(str(qb_expense_data[1] or 0)),
        'qb_count': qb_expense_data[2] or 0
    }

def calculate_payroll_taxes_2012(conn):
    """Calculate 2012 payroll taxes and employment costs."""
    cur = conn.cursor()
    
    # Driver payroll summary
    cur.execute("""
        SELECT SUM(gross_pay) as total_wages,
               SUM(cpp) as total_cpp,
               SUM(ei) as total_ei,
               SUM(tax) as total_income_tax,
               SUM(net_pay) as net_payroll,
               SUM(wcb_payment) as wcb_payments,
               COUNT(*) as payroll_entries
        FROM driver_payroll 
        WHERE year = 2012
    """)
    
    payroll_summary = cur.fetchone()
    
    cur.close()
    
    tax_rates = get_2012_tax_rates()
    
    total_wages = Decimal(str(payroll_summary[0] or 0))
    employer_cpp = total_wages * (tax_rates['cpp_rate'] / 2)  # Employer portion
    employer_ei = total_wages * (tax_rates['ei_rate'] * Decimal('1.4') / 2)  # Employer EI rate is 1.4x employee rate
    
    return {
        'total_wages': total_wages,
        'employee_cpp': Decimal(str(payroll_summary[1] or 0)),
        'employee_ei': Decimal(str(payroll_summary[2] or 0)),
        'income_tax_withheld': Decimal(str(payroll_summary[3] or 0)),
        'net_payroll': Decimal(str(payroll_summary[4] or 0)),
        'wcb_payments': Decimal(str(payroll_summary[5] or 0)),
        'payroll_entries': payroll_summary[6] or 0,
        
        'employer_cpp': employer_cpp,
        'employer_ei': employer_ei,
        'total_employment_costs': total_wages + employer_cpp + employer_ei
    }

def calculate_corporate_tax_2012(taxable_income, tax_rates):
    """Calculate 2012 corporate income tax using exact rates."""
    
    if taxable_income <= 0:
        return {
            'small_business_income': Decimal('0'),
            'general_business_income': Decimal('0'),
            'small_business_tax': Decimal('0'),
            'general_business_tax': Decimal('0'),
            'total_corporate_tax': Decimal('0'),
            'effective_rate': Decimal('0')
        }
    
    small_business_limit = tax_rates['small_business_limit']
    
    if taxable_income <= small_business_limit:
        # All income qualifies for small business rate
        small_business_income = taxable_income
        general_business_income = Decimal('0')
        small_business_tax = taxable_income * tax_rates['combined_small_business']
        general_business_tax = Decimal('0')
    else:
        # Income exceeds small business limit
        small_business_income = small_business_limit
        general_business_income = taxable_income - small_business_limit
        small_business_tax = small_business_limit * tax_rates['combined_small_business']
        general_business_tax = general_business_income * tax_rates['combined_general']
    
    total_corporate_tax = small_business_tax + general_business_tax
    effective_rate = (total_corporate_tax / taxable_income) if taxable_income > 0 else Decimal('0')
    
    return {
        'small_business_income': small_business_income,
        'general_business_income': general_business_income,
        'small_business_tax': small_business_tax,
        'general_business_tax': general_business_tax,
        'total_corporate_tax': total_corporate_tax,
        'effective_rate': effective_rate
    }

def calculate_gst_position_2012(revenue_data, expense_data, tax_rates):
    """Calculate 2012 GST position (owe vs refund)."""
    
    # GST collected on taxable supplies
    gst_collected = revenue_data['banking_gst']
    
    # Add GST on charter revenue (5% of net charter revenue)
    charter_gst_collected = revenue_data['charter_paid'] * tax_rates['gst_rate'] / (1 + tax_rates['gst_rate'])
    
    total_gst_collected = gst_collected + charter_gst_collected
    
    # Input Tax Credits (GST paid on business purchases)
    gst_paid = (expense_data['vehicle_gst_paid'] + 
                expense_data['qb_gst_paid'])
    
    # Net GST position
    net_gst = total_gst_collected - gst_paid
    
    return {
        'gst_on_banking_revenue': gst_collected,
        'gst_on_charter_revenue': charter_gst_collected,
        'total_gst_collected': total_gst_collected,
        'input_tax_credits': gst_paid,
        'net_gst_position': net_gst,
        'gst_status': 'OWE' if net_gst > 0 else 'REFUND',
        'gst_amount_due': net_gst if net_gst > 0 else Decimal('0'),
        'gst_refund_due': abs(net_gst) if net_gst < 0 else Decimal('0')
    }

def main():
    conn = get_db_connection()
    
    try:
        print("🇨🇦 ARROW LIMOUSINE 2012 TAX CALCULATION")
        print("Using Official 2012 Canadian Tax Rates")
        print("=" * 50)
        print(f"Calculation Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Get 2012 tax rates
        tax_rates = get_2012_tax_rates()
        
        print("📋 2012 CANADIAN TAX RATES (ALBERTA)")
        print("===================================")
        print(f"Federal Small Business Rate: {tax_rates['federal_small_business']:.1%}")
        print(f"Alberta Small Business Rate: {tax_rates['alberta_small_business']:.1%}")
        print(f"Combined Small Business Rate: {tax_rates['combined_small_business']:.1%}")
        print(f"Small Business Limit: ${tax_rates['small_business_limit']:,.0f}")
        print(f"GST Rate (Alberta): {tax_rates['gst_rate']:.1%}")
        print(f"Federal General Corporate: {tax_rates['federal_general']:.1%}")
        print(f"Alberta General Corporate: {tax_rates['alberta_general']:.1%}")
        print(f"Combined General Rate: {tax_rates['combined_general']:.1%}")
        print()
        
        # Calculate business revenue
        revenue_data = calculate_business_revenue_2012(conn)
        
        print("💰 2012 BUSINESS REVENUE")
        print("=======================")
        print(f"Banking Revenue (Classified): ${revenue_data['banking_gross']:,.2f}")
        print(f"  • GST Collected: ${revenue_data['banking_gst']:,.2f}")
        print(f"  • Net Revenue: ${revenue_data['banking_net']:,.2f}")
        print(f"  • Transactions: {revenue_data['banking_count']:,}")
        print()
        print(f"Charter Operations: ${revenue_data['charter_revenue']:,.2f}")
        print(f"  • Charter Payments Received: ${revenue_data['charter_paid']:,.2f}")
        print(f"  • Charter Bookings: {revenue_data['charter_count']:,}")
        print()
        print(f"Credit Card Processing: ${revenue_data['card_revenue']:,.2f}")
        print(f"  • Card Transactions: {revenue_data['card_count']:,}")
        print()
        
        # Total taxable business income
        total_business_income = (revenue_data['banking_net'] + 
                               revenue_data['charter_paid'] + 
                               revenue_data['card_revenue'])
        
        print(f"TOTAL TAXABLE BUSINESS INCOME: ${total_business_income:,.2f}")
        print()
        
        # Calculate business expenses
        expense_data = calculate_business_expenses_2012(conn)
        
        print("💸 2012 DEDUCTIBLE BUSINESS EXPENSES")
        print("===================================")
        print(f"Vehicle & Transportation: ${expense_data['vehicle_expenses']:,.2f}")
        print(f"  • Vehicle GST Paid: ${expense_data['vehicle_gst_paid']:,.2f}")
        print(f"  • Vehicle Transactions: {expense_data['vehicle_count']:,}")
        print()
        print(f"Banking & Financial Fees: ${expense_data['banking_expenses']:,.2f}")
        print(f"  • Banking Transactions: {expense_data['banking_count']:,}")
        print()
        print(f"QuickBooks Expenses: ${expense_data['qb_expenses']:,.2f}")
        print(f"  • QB GST Paid: ${expense_data['qb_gst_paid']:,.2f}")
        print(f"  • QB Transactions: {expense_data['qb_count']:,}")
        print()
        
        total_deductible_expenses = (expense_data['vehicle_expenses'] + 
                                   expense_data['banking_expenses'] + 
                                   expense_data['qb_expenses'])
        
        print(f"TOTAL DEDUCTIBLE EXPENSES: ${total_deductible_expenses:,.2f}")
        print()
        
        # Calculate payroll costs
        payroll_data = calculate_payroll_taxes_2012(conn)
        
        print("👥 2012 EMPLOYMENT COSTS")
        print("=======================")
        print(f"Total Wages Paid: ${payroll_data['total_wages']:,.2f}")
        print(f"Income Tax Withheld: ${payroll_data['income_tax_withheld']:,.2f}")
        print(f"Employee CPP: ${payroll_data['employee_cpp']:,.2f}")
        print(f"Employee EI: ${payroll_data['employee_ei']:,.2f}")
        print(f"Employer CPP: ${payroll_data['employer_cpp']:,.2f}")
        print(f"Employer EI: ${payroll_data['employer_ei']:,.2f}")
        print(f"WCB Payments: ${payroll_data['wcb_payments']:,.2f}")
        print(f"Net Payroll: ${payroll_data['net_payroll']:,.2f}")
        print(f"Payroll Entries: {payroll_data['payroll_entries']:,}")
        print()
        print(f"TOTAL EMPLOYMENT COSTS: ${payroll_data['total_employment_costs']:,.2f}")
        print()
        
        # Calculate taxable income
        taxable_income = (total_business_income - 
                         total_deductible_expenses - 
                         payroll_data['total_employment_costs'])
        
        print("📊 TAXABLE INCOME CALCULATION")
        print("============================")
        print(f"Total Business Income: ${total_business_income:,.2f}")
        print(f"Less: Deductible Expenses: (${total_deductible_expenses:,.2f})")
        print(f"Less: Employment Costs: (${payroll_data['total_employment_costs']:,.2f})")
        print("-" * 45)
        print(f"TAXABLE INCOME: ${taxable_income:,.2f}")
        print()
        
        # Calculate corporate tax
        corporate_tax = calculate_corporate_tax_2012(taxable_income, tax_rates)
        
        print("🏢 2012 CORPORATE INCOME TAX")
        print("===========================")
        if taxable_income > 0:
            print(f"Small Business Income: ${corporate_tax['small_business_income']:,.2f}")
            print(f"Small Business Tax (14%): ${corporate_tax['small_business_tax']:,.2f}")
            
            if corporate_tax['general_business_income'] > 0:
                print(f"General Business Income: ${corporate_tax['general_business_income']:,.2f}")
                print(f"General Business Tax (25%): ${corporate_tax['general_business_tax']:,.2f}")
            
            print("-" * 35)
            print(f"TOTAL CORPORATE TAX: ${corporate_tax['total_corporate_tax']:,.2f}")
            print(f"Effective Tax Rate: {corporate_tax['effective_rate']:.1%}")
        else:
            print("NO CORPORATE TAX - Business Loss")
            print(f"Tax Loss Carryforward: ${abs(taxable_income):,.2f}")
        print()
        
        # Calculate GST position
        gst_position = calculate_gst_position_2012(revenue_data, expense_data, tax_rates)
        
        print("🧾 2012 GST ANALYSIS")
        print("===================")
        print(f"GST Collected (Banking): ${gst_position['gst_on_banking_revenue']:,.2f}")
        print(f"GST Collected (Charters): ${gst_position['gst_on_charter_revenue']:,.2f}")
        print(f"Total GST Collected: ${gst_position['total_gst_collected']:,.2f}")
        print(f"Input Tax Credits: ${gst_position['input_tax_credits']:,.2f}")
        print("-" * 30)
        print(f"Net GST Position: ${gst_position['net_gst_position']:,.2f}")
        
        if gst_position['gst_status'] == 'OWE':
            print(f"GST OWING: ${gst_position['gst_amount_due']:,.2f}")
        else:
            print(f"GST REFUND DUE: ${gst_position['gst_refund_due']:,.2f}")
        print()
        
        # Final tax position
        print("🎯 FINAL 2012 TAX POSITION")
        print("=========================")
        
        if taxable_income > 0:
            print(f"Corporate Income Tax: ${corporate_tax['total_corporate_tax']:,.2f}")
        else:
            print(f"Corporate Income Tax: $0.00 (Loss Year)")
        
        if gst_position['gst_status'] == 'OWE':
            print(f"GST Payable: ${gst_position['gst_amount_due']:,.2f}")
            total_tax_owing = corporate_tax['total_corporate_tax'] + gst_position['gst_amount_due']
            print("-" * 30)
            print(f"TOTAL TAX OWING: ${total_tax_owing:,.2f}")
        else:
            print(f"GST Refund: ${gst_position['gst_refund_due']:,.2f}")
            net_position = corporate_tax['total_corporate_tax'] - gst_position['gst_refund_due']
            print("-" * 30)
            if net_position > 0:
                print(f"NET TAX OWING: ${net_position:,.2f}")
            else:
                print(f"NET REFUND DUE: ${abs(net_position):,.2f}")
        
        # Business performance summary
        print()
        print("📈 2012 BUSINESS PERFORMANCE")
        print("===========================")
        if total_business_income > 0:
            profit_margin = (taxable_income / total_business_income) * 100
            expense_ratio = (total_deductible_expenses / total_business_income) * 100
            payroll_ratio = (payroll_data['total_employment_costs'] / total_business_income) * 100
        else:
            profit_margin = expense_ratio = payroll_ratio = 0
        
        print(f"Revenue: ${total_business_income:,.2f}")
        print(f"Expenses: ${total_deductible_expenses:,.2f} ({expense_ratio:.1f}%)")
        print(f"Payroll: ${payroll_data['total_employment_costs']:,.2f} ({payroll_ratio:.1f}%)")
        print(f"Net Income: ${taxable_income:,.2f} ({profit_margin:.1f}%)")
        
        if taxable_income > 0:
            print(f"Tax Burden: {corporate_tax['effective_rate']:.1%} of income")
        
        print()
        if gst_position['gst_status'] == 'REFUND':
            print(f"💰 CONGRATULATIONS! GST REFUND OF ${gst_position['gst_refund_due']:,.2f} IS DUE!")
        elif corporate_tax['total_corporate_tax'] == 0:
            print("[OK] NO CORPORATE TAX OWING FOR 2012!")
        else:
            print(f"[WARN]  TAX PAYMENT REQUIRED FOR 2012")
    
    except Exception as e:
        print(f"[FAIL] Error calculating 2012 tax position: {e}")
        return 1
    
    finally:
        conn.close()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())