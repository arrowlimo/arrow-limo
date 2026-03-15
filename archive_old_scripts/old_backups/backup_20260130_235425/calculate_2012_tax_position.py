#!/usr/bin/env python3
"""
Arrow Limousine 2012 Tax Year Calculation
========================================

This script calculates the complete tax situation for Arrow Limousine
for the 2012 tax year, determining if taxes are owed or refund is due.

Calculations include:
- Business Income (Revenue)
- Business Expenses (Deductible)
- GST/HST Collected vs Paid
- Corporate Tax Obligations
- Net Tax Position (Owe vs Refund)

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
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def calculate_business_income(conn):
    """Calculate total business income for 2012."""
    cur = conn.cursor()
    
    # Revenue from classified deposits
    cur.execute("""
        SELECT SUM(gross_amount) as total_revenue,
               SUM(gst_amount) as gst_collected,
               SUM(net_amount) as net_revenue,
               COUNT(*) as revenue_transactions
        FROM receipts 
        WHERE EXTRACT(year FROM receipt_date) = 2012
          AND (source_system = 'BANKING_REVENUE' OR vendor_name = 'Business Income')
    """)
    
    revenue_data = cur.fetchone()
    
    # Charter revenue from operations
    cur.execute("""
        SELECT SUM(total_amount_due) as charter_revenue,
               COUNT(*) as charter_count
        FROM charters 
        WHERE EXTRACT(year FROM charter_date) = 2012
          AND status != 'cancelled'
    """)
    
    charter_data = cur.fetchone()
    
    # Square payment revenue
    cur.execute("""
        SELECT SUM(amount) as square_revenue,
               COUNT(*) as square_count
        FROM payments 
        WHERE EXTRACT(year FROM payment_date) = 2012
          AND (payment_method ILIKE '%square%' OR payment_method ILIKE '%card%')
    """)
    
    square_data = cur.fetchone()
    
    cur.close()
    
    return {
        'banking_revenue': Decimal(str(revenue_data[0] or 0)),
        'banking_gst': Decimal(str(revenue_data[1] or 0)),
        'banking_net': Decimal(str(revenue_data[2] or 0)),
        'banking_transactions': revenue_data[3] or 0,
        'charter_revenue': Decimal(str(charter_data[0] or 0)),
        'charter_count': charter_data[1] or 0,
        'square_revenue': Decimal(str(square_data[0] or 0)),
        'square_count': square_data[1] or 0
    }

def calculate_business_expenses(conn):
    """Calculate total deductible business expenses for 2012."""
    cur = conn.cursor()
    
    # Vehicle expenses
    cur.execute("""
        SELECT SUM(gross_amount) as vehicle_expenses,
               SUM(gst_amount) as vehicle_gst,
               COUNT(*) as vehicle_transactions
        FROM receipts 
        WHERE EXTRACT(year FROM receipt_date) = 2012
          AND (category ILIKE '%vehicle%' OR category ILIKE '%fuel%' 
               OR vendor_name ILIKE '%woodridge%ford%'
               OR description ILIKE '%vehicle%')
    """)
    
    vehicle_data = cur.fetchone()
    
    # Banking fees (business expenses)
    cur.execute("""
        SELECT SUM(gross_amount) as banking_fees,
               COUNT(*) as fee_transactions
        FROM receipts 
        WHERE EXTRACT(year FROM receipt_date) = 2012
          AND category ILIKE '%banking%'
    """)
    
    banking_data = cur.fetchone()
    
    # Insurance expenses
    cur.execute("""
        SELECT SUM(gross_amount) as insurance_expenses,
               SUM(gst_amount) as insurance_gst,
               COUNT(*) as insurance_transactions
        FROM receipts 
        WHERE EXTRACT(year FROM receipt_date) = 2012
          AND (vendor_name ILIKE '%insurance%' OR category ILIKE '%insurance%'
               OR description ILIKE '%insurance%')
    """)
    
    insurance_data = cur.fetchone()
    
    # Office and general business expenses
    cur.execute("""
        SELECT SUM(gross_amount) as office_expenses,
               SUM(gst_amount) as office_gst,
               COUNT(*) as office_transactions
        FROM receipts 
        WHERE EXTRACT(year FROM receipt_date) = 2012
          AND (category ILIKE '%office%' OR category ILIKE '%supplies%'
               OR category ILIKE '%communication%' OR category ILIKE '%rent%')
    """)
    
    office_data = cur.fetchone()
    
    # Fuel expenses (specific category)
    cur.execute("""
        SELECT SUM(gross_amount) as fuel_expenses,
               SUM(gst_amount) as fuel_gst,
               COUNT(*) as fuel_transactions
        FROM receipts 
        WHERE EXTRACT(year FROM receipt_date) = 2012
          AND (category ILIKE '%fuel%' OR vendor_name ILIKE '%shell%' 
               OR vendor_name ILIKE '%petro%' OR vendor_name ILIKE '%esso%')
    """)
    
    fuel_data = cur.fetchone()
    
    cur.close()
    
    return {
        'vehicle_expenses': Decimal(str(vehicle_data[0] or 0)),
        'vehicle_gst': Decimal(str(vehicle_data[1] or 0)),
        'vehicle_count': vehicle_data[2] or 0,
        'banking_fees': Decimal(str(banking_data[0] or 0)),
        'banking_count': banking_data[1] or 0,
        'insurance_expenses': Decimal(str(insurance_data[0] or 0)),
        'insurance_gst': Decimal(str(insurance_data[1] or 0)),
        'insurance_count': insurance_data[2] or 0,
        'office_expenses': Decimal(str(office_data[0] or 0)),
        'office_gst': Decimal(str(office_data[1] or 0)),
        'office_count': office_data[2] or 0,
        'fuel_expenses': Decimal(str(fuel_data[0] or 0)),
        'fuel_gst': Decimal(str(fuel_data[1] or 0)),
        'fuel_count': fuel_data[2] or 0
    }

def calculate_payroll_expenses(conn):
    """Calculate payroll and employment expenses for 2012."""
    cur = conn.cursor()
    
    # Driver payroll
    cur.execute("""
        SELECT SUM(gross_pay) as total_wages,
               SUM(cpp + ei + tax) as total_deductions,
               SUM(net_pay) as net_wages,
               COUNT(*) as payroll_entries
        FROM driver_payroll 
        WHERE year = 2012
    """)
    
    payroll_data = cur.fetchone()
    
    # WCB payments
    cur.execute("""
        SELECT SUM(wcb_payment) as wcb_total
        FROM driver_payroll 
        WHERE year = 2012 AND wcb_payment IS NOT NULL
    """)
    
    wcb_data = cur.fetchone()
    
    cur.close()
    
    return {
        'total_wages': Decimal(str(payroll_data[0] or 0)),
        'total_deductions': Decimal(str(payroll_data[1] or 0)),
        'net_wages': Decimal(str(payroll_data[2] or 0)),
        'payroll_entries': payroll_data[3] or 0,
        'wcb_payments': Decimal(str(wcb_data[0] or 0))
    }

def calculate_corporate_tax_rates():
    """Alberta corporate tax rates for 2012."""
    return {
        'federal_small_business': Decimal('0.11'),      # 11% federal small business
        'alberta_small_business': Decimal('0.03'),      # 3% Alberta small business
        'combined_small_business': Decimal('0.14'),     # 14% combined small business rate
        'federal_general': Decimal('0.15'),             # 15% federal general rate
        'alberta_general': Decimal('0.10'),             # 10% Alberta general rate
        'combined_general': Decimal('0.25'),            # 25% combined general rate
        'small_business_limit': Decimal('400000')       # $400,000 small business limit
    }

def calculate_gst_position(income_data, expense_data):
    """Calculate GST owing or refund position."""
    
    # GST collected on revenue
    gst_collected = income_data['banking_gst']
    
    # GST paid on expenses (Input Tax Credits)
    gst_paid = (expense_data['vehicle_gst'] + expense_data['insurance_gst'] + 
                expense_data['office_gst'] + expense_data['fuel_gst'])
    
    # Net GST position (positive = owe, negative = refund)
    net_gst = gst_collected - gst_paid
    
    return {
        'gst_collected': gst_collected,
        'gst_paid': gst_paid,
        'net_gst_position': net_gst,
        'gst_status': 'OWE' if net_gst > 0 else 'REFUND',
        'gst_amount': abs(net_gst)
    }

def main():
    conn = get_db_connection()
    
    try:
        print("🧮 ARROW LIMOUSINE 2012 TAX CALCULATION")
        print("=" * 45)
        print(f"Calculation Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Calculate business income
        income_data = calculate_business_income(conn)
        
        print("💰 BUSINESS INCOME ANALYSIS")
        print("==========================")
        print(f"Banking Revenue: ${income_data['banking_revenue']:,.2f}")
        print(f"  • GST Collected: ${income_data['banking_gst']:,.2f}")
        print(f"  • Net Revenue: ${income_data['banking_net']:,.2f}")
        print(f"  • Transactions: {income_data['banking_transactions']:,}")
        print()
        print(f"Charter Operations: ${income_data['charter_revenue']:,.2f}")
        print(f"  • Charter Count: {income_data['charter_count']:,}")
        print()
        print(f"Square Card Processing: ${income_data['square_revenue']:,.2f}")
        print(f"  • Square Transactions: {income_data['square_count']:,}")
        print()
        
        total_gross_income = (income_data['banking_revenue'] + 
                             income_data['charter_revenue'] + 
                             income_data['square_revenue'])
        print(f"TOTAL GROSS BUSINESS INCOME: ${total_gross_income:,.2f}")
        print()
        
        # Calculate business expenses
        expense_data = calculate_business_expenses(conn)
        
        print("💸 BUSINESS EXPENSE ANALYSIS")
        print("===========================")
        print(f"Vehicle Expenses: ${expense_data['vehicle_expenses']:,.2f}")
        print(f"  • Vehicle GST Paid: ${expense_data['vehicle_gst']:,.2f}")
        print(f"  • Transactions: {expense_data['vehicle_count']:,}")
        print()
        print(f"Banking Fees: ${expense_data['banking_fees']:,.2f}")
        print(f"  • Fee Transactions: {expense_data['banking_count']:,}")
        print()
        print(f"Insurance Expenses: ${expense_data['insurance_expenses']:,.2f}")
        print(f"  • Insurance GST: ${expense_data['insurance_gst']:,.2f}")
        print(f"  • Transactions: {expense_data['insurance_count']:,}")
        print()
        print(f"Office Expenses: ${expense_data['office_expenses']:,.2f}")
        print(f"  • Office GST: ${expense_data['office_gst']:,.2f}")
        print(f"  • Transactions: {expense_data['office_count']:,}")
        print()
        print(f"Fuel Expenses: ${expense_data['fuel_expenses']:,.2f}")
        print(f"  • Fuel GST: ${expense_data['fuel_gst']:,.2f}")
        print(f"  • Transactions: {expense_data['fuel_count']:,}")
        print()
        
        total_expenses = (expense_data['vehicle_expenses'] + 
                         expense_data['banking_fees'] + 
                         expense_data['insurance_expenses'] + 
                         expense_data['office_expenses'] + 
                         expense_data['fuel_expenses'])
        print(f"TOTAL BUSINESS EXPENSES: ${total_expenses:,.2f}")
        print()
        
        # Calculate payroll expenses
        payroll_data = calculate_payroll_expenses(conn)
        
        print("👥 PAYROLL & EMPLOYMENT EXPENSES")
        print("===============================")
        print(f"Total Wages Paid: ${payroll_data['total_wages']:,.2f}")
        print(f"Payroll Deductions: ${payroll_data['total_deductions']:,.2f}")
        print(f"Net Wages: ${payroll_data['net_wages']:,.2f}")
        print(f"Payroll Entries: {payroll_data['payroll_entries']:,}")
        print(f"WCB Payments: ${payroll_data['wcb_payments']:,.2f}")
        print()
        
        # Calculate net business income
        net_business_income = total_gross_income - total_expenses - payroll_data['total_wages']
        
        print("📊 NET BUSINESS INCOME CALCULATION")
        print("=================================")
        print(f"Gross Business Income: ${total_gross_income:,.2f}")
        print(f"Less: Business Expenses: (${total_expenses:,.2f})")
        print(f"Less: Wage Expenses: (${payroll_data['total_wages']:,.2f})")
        print("-" * 40)
        print(f"NET BUSINESS INCOME: ${net_business_income:,.2f}")
        print()
        
        # Calculate corporate tax
        tax_rates = calculate_corporate_tax_rates()
        
        if net_business_income <= tax_rates['small_business_limit']:
            applicable_rate = tax_rates['combined_small_business']
            tax_type = "Small Business Rate"
        else:
            small_business_tax = tax_rates['small_business_limit'] * tax_rates['combined_small_business']
            excess_income = net_business_income - tax_rates['small_business_limit']
            excess_tax = excess_income * tax_rates['combined_general']
            applicable_rate = tax_rates['combined_general']
            tax_type = "General Business Rate"
        
        if net_business_income > 0:
            if net_business_income <= tax_rates['small_business_limit']:
                corporate_tax_owed = net_business_income * applicable_rate
            else:
                corporate_tax_owed = small_business_tax + excess_tax
        else:
            corporate_tax_owed = Decimal('0')
        
        print("🏢 CORPORATE TAX CALCULATION")
        print("===========================")
        print(f"Net Business Income: ${net_business_income:,.2f}")
        print(f"Applicable Tax Rate: {applicable_rate:.1%} ({tax_type})")
        print(f"Corporate Tax Owed: ${corporate_tax_owed:,.2f}")
        print()
        
        # Calculate GST position
        gst_analysis = calculate_gst_position(income_data, expense_data)
        
        print("🧾 GST/HST ANALYSIS")
        print("==================")
        print(f"GST Collected on Sales: ${gst_analysis['gst_collected']:,.2f}")
        print(f"GST Paid on Purchases: ${gst_analysis['gst_paid']:,.2f}")
        print("-" * 30)
        print(f"Net GST Position: ${gst_analysis['net_gst_position']:,.2f}")
        print(f"GST Status: {gst_analysis['gst_status']} ${gst_analysis['gst_amount']:,.2f}")
        print()
        
        # Final tax summary
        total_tax_owed = corporate_tax_owed
        if gst_analysis['gst_status'] == 'OWE':
            total_tax_owed += gst_analysis['gst_amount']
        
        print("🎯 FINAL TAX POSITION SUMMARY")
        print("============================")
        print(f"Corporate Tax Owed: ${corporate_tax_owed:,.2f}")
        if gst_analysis['gst_status'] == 'OWE':
            print(f"GST Owed: ${gst_analysis['gst_amount']:,.2f}")
            print("-" * 30)
            print(f"TOTAL TAX OWED: ${total_tax_owed:,.2f}")
        else:
            print(f"GST Refund Due: ${gst_analysis['gst_amount']:,.2f}")
            print("-" * 30)
            net_position = corporate_tax_owed - gst_analysis['gst_amount']
            if net_position > 0:
                print(f"NET TAX OWED: ${net_position:,.2f}")
            else:
                print(f"NET REFUND DUE: ${abs(net_position):,.2f}")
        print()
        
        # Business performance metrics
        if total_gross_income > 0:
            profit_margin = (net_business_income / total_gross_income) * 100
            tax_rate_effective = (corporate_tax_owed / net_business_income) * 100 if net_business_income > 0 else 0
        else:
            profit_margin = 0
            tax_rate_effective = 0
        
        print("📈 BUSINESS PERFORMANCE METRICS")
        print("==============================")
        print(f"Gross Revenue: ${total_gross_income:,.2f}")
        print(f"Net Profit: ${net_business_income:,.2f}")
        print(f"Profit Margin: {profit_margin:.1f}%")
        print(f"Effective Tax Rate: {tax_rate_effective:.1f}%")
        print(f"Total Expense Ratio: {(total_expenses + payroll_data['total_wages']) / total_gross_income * 100:.1f}%")
        
        if gst_analysis['gst_status'] == 'OWE' and total_tax_owed > 0:
            print(f"\n[WARN]  TAX PAYMENT REQUIRED: ${total_tax_owed:,.2f}")
        elif gst_analysis['gst_status'] == 'REFUND':
            print(f"\n💰 TAX REFUND AVAILABLE: ${gst_analysis['gst_amount']:,.2f}")
        else:
            print(f"\n[OK] MINIMAL TAX POSITION")
    
    except Exception as e:
        print(f"[FAIL] Error calculating tax position: {e}")
        return 1
    
    finally:
        conn.close()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())