#!/usr/bin/env python3
"""
Create Comprehensive Chart of Accounts for Arrow Limousine
Blends standard accounting numbering with QuickBooks structure and business-specific needs
"""

import psycopg2
import os
import sys
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def save_progress(step_name, data):
    """Save progress for each step."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_dir = 'l:\\limo\\data\\chart_of_accounts_setup'
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'{timestamp}_{step_name}.txt')
    
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"Step: {step_name}\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write("=" * 100 + "\n\n")
        f.write(data)
    
    print(f"✓ Progress saved: {log_file}")

# Comprehensive Chart of Accounts for Limousine Business
CHART_OF_ACCOUNTS = [
    # ========================================
    # ASSETS (1000-1999)
    # ========================================
    {'code': '1000', 'name': 'Assets', 'type': 'Asset', 'qb_type': 'OtherCurrentAsset', 'parent': None, 'level': 0, 'is_header': True, 
     'normal_balance': 'DEBIT', 'description': 'All company assets'},
    
    # Cash & Bank Accounts (1000-1099)
    {'code': '1010', 'name': 'Cash & Bank Accounts', 'type': 'Asset', 'qb_type': 'Bank', 'parent': '1000', 'level': 1, 'is_header': True,
     'normal_balance': 'DEBIT', 'description': 'All cash and banking accounts'},
    {'code': '1011', 'name': 'CIBC Checking 0228362', 'type': 'Asset', 'qb_type': 'Bank', 'parent': '1010', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Primary operating account', 'bank_account': '0228362'},
    {'code': '1012', 'name': 'Scotia Bank 903990106011', 'type': 'Asset', 'qb_type': 'Bank', 'parent': '1010', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Secondary business account', 'bank_account': '903990106011'},
    {'code': '1015', 'name': 'Petty Cash', 'type': 'Asset', 'qb_type': 'OtherCurrentAsset', 'parent': '1010', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Cash box for driver floats and reimbursements'},
    {'code': '1016', 'name': 'Driver Float Outstanding', 'type': 'Asset', 'qb_type': 'OtherCurrentAsset', 'parent': '1010', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Cash floats issued to drivers'},
    {'code': '1018', 'name': 'Undeposited Funds', 'type': 'Asset', 'qb_type': 'OtherCurrentAsset', 'parent': '1010', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Cash and checks awaiting deposit'},
    
    # Accounts Receivable (1100-1199)
    {'code': '1100', 'name': 'Accounts Receivable', 'type': 'Asset', 'qb_type': 'AccountsReceivable', 'parent': '1000', 'level': 1, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Customer invoices outstanding'},
    
    # Prepaid Expenses (1200-1299)
    {'code': '1200', 'name': 'Prepaid Expenses', 'type': 'Asset', 'qb_type': 'OtherCurrentAsset', 'parent': '1000', 'level': 1, 'is_header': True,
     'normal_balance': 'DEBIT', 'description': 'Expenses paid in advance'},
    {'code': '1201', 'name': 'Prepaid Insurance', 'type': 'Asset', 'qb_type': 'OtherCurrentAsset', 'parent': '1200', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Insurance premiums paid in advance'},
    {'code': '1202', 'name': 'Prepaid Rent', 'type': 'Asset', 'qb_type': 'OtherCurrentAsset', 'parent': '1200', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Rent paid in advance'},
    {'code': '1203', 'name': 'Prepaid Licenses & Permits', 'type': 'Asset', 'qb_type': 'OtherCurrentAsset', 'parent': '1200', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Annual licenses and permits prepaid'},
    
    # Fixed Assets - Vehicles (1400-1499)
    {'code': '1400', 'name': 'Fixed Assets - Vehicles', 'type': 'Asset', 'qb_type': 'FixedAsset', 'parent': '1000', 'level': 1, 'is_header': True,
     'normal_balance': 'DEBIT', 'description': 'Limousine fleet assets'},
    {'code': '1410', 'name': 'Vehicles - Cost', 'type': 'Asset', 'qb_type': 'FixedAsset', 'parent': '1400', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Original cost of all vehicles'},
    {'code': '1420', 'name': 'Vehicles - Accumulated Depreciation', 'type': 'Asset', 'qb_type': 'FixedAsset', 'parent': '1400', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Contra-asset: accumulated depreciation on fleet'},
    
    # Fixed Assets - Equipment (1500-1599)
    {'code': '1500', 'name': 'Fixed Assets - Equipment', 'type': 'Asset', 'qb_type': 'FixedAsset', 'parent': '1000', 'level': 1, 'is_header': True,
     'normal_balance': 'DEBIT', 'description': 'Office and business equipment'},
    {'code': '1510', 'name': 'Office Equipment - Cost', 'type': 'Asset', 'qb_type': 'FixedAsset', 'parent': '1500', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Computers, furniture, etc.'},
    {'code': '1520', 'name': 'Office Equipment - Accumulated Depreciation', 'type': 'Asset', 'qb_type': 'FixedAsset', 'parent': '1500', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Contra-asset: accumulated depreciation on equipment'},
    
    # ========================================
    # LIABILITIES (2000-2999)
    # ========================================
    {'code': '2000', 'name': 'Liabilities', 'type': 'Liability', 'qb_type': 'OtherCurrentLiability', 'parent': None, 'level': 0, 'is_header': True,
     'normal_balance': 'CREDIT', 'description': 'All company liabilities'},
    
    # Accounts Payable (2000-2099)
    {'code': '2010', 'name': 'Accounts Payable', 'type': 'Liability', 'qb_type': 'AccountsPayable', 'parent': '2000', 'level': 1, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Vendor bills outstanding'},
    
    # Credit Cards (2100-2199)
    {'code': '2100', 'name': 'Credit Cards', 'type': 'Liability', 'qb_type': 'CreditCard', 'parent': '2000', 'level': 1, 'is_header': True,
     'normal_balance': 'CREDIT', 'description': 'Credit card liabilities'},
    {'code': '2110', 'name': 'Amex Business Card', 'type': 'Liability', 'qb_type': 'CreditCard', 'parent': '2100', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'American Express business card'},
    {'code': '2120', 'name': 'Visa Business Card', 'type': 'Liability', 'qb_type': 'CreditCard', 'parent': '2100', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Visa business card'},
    
    # Vehicle Loans & Leases (2200-2299)
    {'code': '2200', 'name': 'Vehicle Loans & Leases', 'type': 'Liability', 'qb_type': 'LongTermLiability', 'parent': '2000', 'level': 1, 'is_header': True,
     'normal_balance': 'CREDIT', 'description': 'Vehicle financing and leases'},
    {'code': '2210', 'name': 'Heffner Auto Finance', 'type': 'Liability', 'qb_type': 'LongTermLiability', 'parent': '2200', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Vehicle loans from Heffner'},
    {'code': '2220', 'name': 'Vehicle Operating Leases', 'type': 'Liability', 'qb_type': 'LongTermLiability', 'parent': '2200', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Operating leases for fleet'},
    
    # Payroll Liabilities (2300-2399)
    {'code': '2300', 'name': 'Payroll Liabilities', 'type': 'Liability', 'qb_type': 'OtherCurrentLiability', 'parent': '2000', 'level': 1, 'is_header': True,
     'normal_balance': 'CREDIT', 'description': 'Payroll taxes and deductions'},
    {'code': '2310', 'name': 'Payroll Taxes Payable - CPP', 'type': 'Liability', 'qb_type': 'OtherCurrentLiability', 'parent': '2300', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Canada Pension Plan payable'},
    {'code': '2320', 'name': 'Payroll Taxes Payable - EI', 'type': 'Liability', 'qb_type': 'OtherCurrentLiability', 'parent': '2300', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Employment Insurance payable'},
    {'code': '2330', 'name': 'Payroll Taxes Payable - Income Tax', 'type': 'Liability', 'qb_type': 'OtherCurrentLiability', 'parent': '2300', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Federal/provincial income tax withheld'},
    {'code': '2340', 'name': 'WCB Payable', 'type': 'Liability', 'qb_type': 'OtherCurrentLiability', 'parent': '2300', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Workers Compensation Board premiums'},
    
    # Sales Tax Payable (2400-2499)
    {'code': '2400', 'name': 'Sales Tax Payable', 'type': 'Liability', 'qb_type': 'OtherCurrentLiability', 'parent': '2000', 'level': 1, 'is_header': True,
     'normal_balance': 'CREDIT', 'description': 'GST/HST collected from customers'},
    {'code': '2410', 'name': 'GST/HST Payable', 'type': 'Liability', 'qb_type': 'OtherCurrentLiability', 'parent': '2400', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'GST/HST collected from customers'},
    {'code': '2420', 'name': 'GST/HST Paid on Purchases', 'type': 'Liability', 'qb_type': 'OtherCurrentLiability', 'parent': '2400', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Input tax credits - GST paid on expenses'},
    
    # ========================================
    # EQUITY (3000-3999)
    # ========================================
    {'code': '3000', 'name': 'Equity', 'type': 'Equity', 'qb_type': 'Equity', 'parent': None, 'level': 0, 'is_header': True,
     'normal_balance': 'CREDIT', 'description': 'Owner equity accounts'},
    {'code': '3010', 'name': "Owner's Capital", 'type': 'Equity', 'qb_type': 'Equity', 'parent': '3000', 'level': 1, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Owner investment in business'},
    {'code': '3020', 'name': "Owner's Draw", 'type': 'Equity', 'qb_type': 'Equity', 'parent': '3000', 'level': 1, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Owner withdrawals from business'},
    {'code': '3030', 'name': 'Retained Earnings', 'type': 'Equity', 'qb_type': 'Equity', 'parent': '3000', 'level': 1, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Accumulated profits/losses'},
    
    # ========================================
    # INCOME / REVENUE (4000-4999)
    # ========================================
    {'code': '4000', 'name': 'Income', 'type': 'Income', 'qb_type': 'Income', 'parent': None, 'level': 0, 'is_header': True,
     'normal_balance': 'CREDIT', 'description': 'All revenue sources'},
    
    # Charter Revenue (4000-4099)
    {'code': '4010', 'name': 'Charter Revenue', 'type': 'Income', 'qb_type': 'Income', 'parent': '4000', 'level': 1, 'is_header': True,
     'normal_balance': 'CREDIT', 'description': 'Limousine service revenue'},
    {'code': '4011', 'name': 'Hourly Charter Revenue', 'type': 'Income', 'qb_type': 'Income', 'parent': '4010', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Hourly charter bookings'},
    {'code': '4012', 'name': 'Airport Transfer Revenue', 'type': 'Income', 'qb_type': 'Income', 'parent': '4010', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Airport pickup/dropoff services'},
    {'code': '4013', 'name': 'Package Rate Revenue', 'type': 'Income', 'qb_type': 'Income', 'parent': '4010', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Special event packages (weddings, proms, etc.)'},
    {'code': '4014', 'name': 'Extra Time Revenue', 'type': 'Income', 'qb_type': 'Income', 'parent': '4010', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Overtime charges'},
    
    # Additional Revenue (4100-4199)
    {'code': '4100', 'name': 'Additional Revenue', 'type': 'Income', 'qb_type': 'Income', 'parent': '4000', 'level': 1, 'is_header': True,
     'normal_balance': 'CREDIT', 'description': 'Other income sources'},
    {'code': '4110', 'name': 'Gratuities', 'type': 'Income', 'qb_type': 'Income', 'parent': '4100', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Tips and gratuities (GST-exempt)'},
    {'code': '4115', 'name': 'Beverage Service Charges', 'type': 'Income', 'qb_type': 'Income', 'parent': '4100', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Charges to customers for beverages provided (compare to 5310 cost)'},
    {'code': '4120', 'name': 'Fuel Surcharge Income', 'type': 'Income', 'qb_type': 'Income', 'parent': '4100', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Fuel surcharges passed to customers'},
    {'code': '4130', 'name': 'Late Cancellation Fees', 'type': 'Income', 'qb_type': 'Income', 'parent': '4100', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Cancellation and no-show fees'},
    {'code': '4135', 'name': 'Trade of Services - Income', 'type': 'Income', 'qb_type': 'Income', 'parent': '4100', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Fair market value of services received in trade (e.g., Fibrenew rent)'},
    {'code': '4140', 'name': 'Interest Income', 'type': 'Income', 'qb_type': 'OtherIncome', 'parent': '4100', 'level': 2, 'is_header': False,
     'normal_balance': 'CREDIT', 'description': 'Bank interest earned'},
    
    # ========================================
    # EXPENSES (5000-5999)
    # ========================================
    {'code': '5000', 'name': 'Expenses', 'type': 'Expense', 'qb_type': 'Expense', 'parent': None, 'level': 0, 'is_header': True,
     'normal_balance': 'DEBIT', 'description': 'All business expenses'},
    
    # Vehicle Operating Expenses (5100-5199)
    {'code': '5100', 'name': 'Vehicle Operating Expenses', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5000', 'level': 1, 'is_header': True,
     'normal_balance': 'DEBIT', 'description': 'Fleet operation costs'},
    {'code': '5110', 'name': 'Fuel Expense', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5100', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Gasoline and diesel fuel'},
    {'code': '5120', 'name': 'Vehicle Maintenance & Repairs', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5100', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Oil changes, repairs, parts'},
    {'code': '5130', 'name': 'Vehicle Insurance', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5100', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Commercial vehicle insurance'},
    {'code': '5140', 'name': 'Vehicle Licenses & Permits', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5100', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Registration, permits, inspections'},
    {'code': '5150', 'name': 'Vehicle Lease Payments', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5100', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Operating lease payments'},
    {'code': '5160', 'name': 'Vehicle Loan Interest', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5100', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Interest on vehicle financing'},
    {'code': '5170', 'name': 'Vehicle Depreciation', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5100', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Depreciation expense on fleet'},
    
    # Driver & Payroll Expenses (5200-5299)
    {'code': '5200', 'name': 'Driver & Payroll Expenses', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5000', 'level': 1, 'is_header': True,
     'normal_balance': 'DEBIT', 'description': 'Labor costs'},
    {'code': '5210', 'name': 'Driver Wages', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5200', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Chauffeur wages and commissions'},
    {'code': '5220', 'name': 'Employee Wages - Office', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5200', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Office staff salaries'},
    {'code': '5230', 'name': 'Payroll Taxes - CPP', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5200', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Employer CPP contributions'},
    {'code': '5240', 'name': 'Payroll Taxes - EI', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5200', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Employer EI contributions'},
    {'code': '5250', 'name': 'WCB Premiums', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5200', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Workers Compensation premiums'},
    
    # Customer Service Expenses (5300-5399)
    {'code': '5300', 'name': 'Customer Service Expenses', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5000', 'level': 1, 'is_header': True,
     'normal_balance': 'DEBIT', 'description': 'Customer amenities and hospitality'},
    {'code': '5310', 'name': 'Beverages - Customer Service', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5300', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Water, pop, chips purchased for limousine service (compare to revenue recovery)'},
    {'code': '5315', 'name': 'Beverages - Business Entertainment', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5300', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Bar/liquor purchases for business meetings, client entertainment (50% deductible)'},
    {'code': '5320', 'name': 'Driver Meals - On Duty', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5300', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Meals for drivers during charter shifts (business expense)'},
    {'code': '5325', 'name': 'Business Meals & Entertainment', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5300', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Client dinners, prospect meetings, networking events (50% deductible CRA)'},
    
    # Office & Administrative (5400-5499)
    {'code': '5400', 'name': 'Office & Administrative', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5000', 'level': 1, 'is_header': True,
     'normal_balance': 'DEBIT', 'description': 'Office operating costs'},
    {'code': '5410', 'name': 'Rent Expense', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5400', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Office/garage rent'},
    {'code': '5420', 'name': 'Office Supplies', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5400', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Stationery, printer supplies, etc.'},
    {'code': '5430', 'name': 'Telephone & Internet', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5400', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Phone and internet services'},
    {'code': '5440', 'name': 'Utilities', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5400', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Electricity, gas, water'},
    {'code': '5450', 'name': 'Equipment Depreciation', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5400', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Office equipment depreciation'},
    
    # Professional Services (5500-5599)
    {'code': '5500', 'name': 'Professional Services', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5000', 'level': 1, 'is_header': True,
     'normal_balance': 'DEBIT', 'description': 'Professional fees'},
    {'code': '5510', 'name': 'Accounting & Bookkeeping', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5500', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Accountant and bookkeeper fees'},
    {'code': '5520', 'name': 'Legal Fees', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5500', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Attorney fees'},
    {'code': '5530', 'name': 'Consulting Fees', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5500', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Business consulting'},
    
    # Marketing & Advertising (5600-5699)
    {'code': '5600', 'name': 'Marketing & Advertising', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5000', 'level': 1, 'is_header': True,
     'normal_balance': 'DEBIT', 'description': 'Marketing and promotional expenses'},
    {'code': '5610', 'name': 'Advertising', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5600', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Print, digital, radio ads'},
    {'code': '5620', 'name': 'Website & Online Marketing', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5600', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Website hosting, SEO, social media'},
    {'code': '5630', 'name': 'Promotional Materials', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5600', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Business cards, brochures, signage'},
    {'code': '5640', 'name': 'Promotional Gifts & Giveaways', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5600', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Client gifts, promotional items, referral incentives'},
    {'code': '5650', 'name': 'Charitable Donations - Business', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5600', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Donations for community relations, event sponsorships (tax receipts issued)'},
    {'code': '5660', 'name': 'Trade of Services', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5600', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Charter services traded for goods/services (FMV basis - e.g., Fibrenew rent exchange)'},
    
    # Banking & Financial (5700-5799)
    {'code': '5700', 'name': 'Banking & Financial', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5000', 'level': 1, 'is_header': True,
     'normal_balance': 'DEBIT', 'description': 'Banking and financial costs'},
    {'code': '5710', 'name': 'Bank Fees & Service Charges', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5700', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Monthly fees, transaction fees'},
    {'code': '5720', 'name': 'Credit Card Processing Fees', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5700', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Merchant fees for card payments'},
    {'code': '5730', 'name': 'Interest Expense', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5700', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Non-vehicle loan interest'},
    
    # Other Expenses (5800-5999)
    {'code': '5800', 'name': 'Other Business Expenses', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5000', 'level': 1, 'is_header': True,
     'normal_balance': 'DEBIT', 'description': 'Miscellaneous and grey-area business expenses'},
    {'code': '5810', 'name': 'Uniforms & Laundry', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5800', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Driver uniforms and cleaning'},
    {'code': '5820', 'name': 'Training & Development', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5800', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Driver training, certifications, safety courses'},
    {'code': '5830', 'name': 'Subscriptions & Memberships', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5800', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Software subscriptions, association dues, business networks'},
    {'code': '5840', 'name': 'Business Development Expenses', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5800', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Networking events, industry conferences, business relationship building'},
    {'code': '5850', 'name': 'Mixed-Use Expenses', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5800', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Expenses with business AND personal use (track allocation % for CRA)'},
    {'code': '5860', 'name': 'Supplies - General Business', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5800', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Business supplies not classified elsewhere (cleaning, tools, etc.)'},
    {'code': '5870', 'name': 'Miscellaneous Business Expense', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5800', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Uncategorized business expenses (review quarterly)'},
    {'code': '5880', 'name': 'Owner Personal (Non-Deductible)', 'type': 'Expense', 'qb_type': 'Expense', 'parent': '5800', 'level': 2, 'is_header': False,
     'normal_balance': 'DEBIT', 'description': 'Personal expenses paid through business (move to Owner Draw quarterly)'},
]

def create_chart_of_accounts_table(cur):
    """Ensure chart_of_accounts table exists with proper structure."""
    print("\n1. Creating/verifying chart_of_accounts table...")
    
    # Create table if doesn't exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chart_of_accounts (
            account_code VARCHAR(20) PRIMARY KEY,
            account_name VARCHAR(100) NOT NULL,
            account_type VARCHAR(30) NOT NULL,
            parent_account VARCHAR(20),
            description TEXT,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Add missing columns if they don't exist
    columns_to_add = [
        ("qb_account_type", "VARCHAR(50)"),
        ("account_level", "INTEGER DEFAULT 0"),
        ("is_header_account", "BOOLEAN DEFAULT false"),
        ("normal_balance", "VARCHAR(10) CHECK (normal_balance IN ('DEBIT', 'CREDIT'))"),
        ("current_balance", "NUMERIC(15,2) DEFAULT 0"),
        ("bank_account_number", "TEXT"),
        ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ]
    
    for col_name, col_def in columns_to_add:
        try:
            cur.execute(f"ALTER TABLE chart_of_accounts ADD COLUMN IF NOT EXISTS {col_name} {col_def}")
        except Exception as e:
            # Column might already exist, continue
            pass
    
    # Create indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chart_accounts_code ON chart_of_accounts(account_code)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chart_accounts_type ON chart_of_accounts(account_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chart_accounts_parent ON chart_of_accounts(parent_account)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chart_accounts_active ON chart_of_accounts(is_active)")
    
    print("  ✓ Table structure verified")

def populate_chart_of_accounts(cur):
    """Populate chart of accounts with comprehensive limousine business structure."""
    print("\n2. Populating chart of accounts...")
    
    inserted = 0
    updated = 0
    
    for account in CHART_OF_ACCOUNTS:
        # Check if account exists
        cur.execute("SELECT account_code FROM chart_of_accounts WHERE account_code = %s", (account['code'],))
        existing = cur.fetchone()
        
        if existing:
            # Update existing account
            cur.execute("""
                UPDATE chart_of_accounts
                SET account_name = %s,
                    account_type = %s,
                    qb_account_type = %s,
                    parent_account = %s,
                    account_level = %s,
                    is_header_account = %s,
                    normal_balance = %s,
                    description = %s,
                    bank_account_number = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE account_code = %s
            """, (
                account['name'],
                account['type'],
                account['qb_type'],
                account.get('parent'),
                account['level'],
                account['is_header'],
                account['normal_balance'],
                account.get('description', ''),
                account.get('bank_account', None),
                account['code']
            ))
            updated += 1
        else:
            # Insert new account
            cur.execute("""
                INSERT INTO chart_of_accounts (
                    account_code, account_name, account_type, qb_account_type,
                    parent_account, account_level, is_header_account,
                    normal_balance, description, bank_account_number
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                account['code'],
                account['name'],
                account['type'],
                account['qb_type'],
                account.get('parent'),
                account['level'],
                account['is_header'],
                account['normal_balance'],
                account.get('description', ''),
                account.get('bank_account', None)
            ))
            inserted += 1
    
    print(f"  ✓ Inserted {inserted} new accounts")
    print(f"  ✓ Updated {updated} existing accounts")
    
    return inserted, updated

def create_category_mapping(cur):
    """Map receipt categories to chart of accounts."""
    print("\n3. Creating receipt category to account mapping...")
    
    # Check if receipt_categories table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'receipt_categories'
        )
    """)
    if not cur.fetchone()[0]:
        print("  ⚠ Category mapping skipped (receipt_categories table may not exist yet)")
        return
    
    cur.execute("""
        UPDATE receipt_categories SET account_code = '5110' WHERE category_code = 'fuel';
        UPDATE receipt_categories SET account_code = '5120' WHERE category_code = 'vehicle_maintenance';
        UPDATE receipt_categories SET account_code = '5120' WHERE category_code = 'vehicle_supplies';
        UPDATE receipt_categories SET account_code = '5320' WHERE category_code = 'driver_meal';
        UPDATE receipt_categories SET account_code = '5310' WHERE category_code = 'customer_beverages';
        UPDATE receipt_categories SET account_code = '5310' WHERE category_code = 'customer_snacks';
        UPDATE receipt_categories SET account_code = '5310' WHERE category_code = 'customer_supplies';
        UPDATE receipt_categories SET account_code = '5315' WHERE category_code = 'beverages_entertainment';
        UPDATE receipt_categories SET account_code = '5325' WHERE category_code = 'meals_entertainment';
        UPDATE receipt_categories SET account_code = '5420' WHERE category_code = 'office_supplies';
        UPDATE receipt_categories SET account_code = '5430' WHERE category_code = 'communication';
        UPDATE receipt_categories SET account_code = '5130' WHERE category_code = 'insurance';
        UPDATE receipt_categories SET account_code = '5150' WHERE category_code = 'vehicle_lease';
        UPDATE receipt_categories SET account_code = '5710' WHERE category_code = 'banking_fees';
        UPDATE receipt_categories SET account_code = '5640' WHERE category_code = 'promotional_gifts';
        UPDATE receipt_categories SET account_code = '5650' WHERE category_code = 'charitable_donation';
        UPDATE receipt_categories SET account_code = '5660' WHERE category_code = 'trade_of_services';
        UPDATE receipt_categories SET account_code = '5840' WHERE category_code = 'business_development';
        UPDATE receipt_categories SET account_code = '5850' WHERE category_code = 'mixed_use';
        UPDATE receipt_categories SET account_code = '5860' WHERE category_code = 'general_supplies';
        UPDATE receipt_categories SET account_code = '5880' WHERE category_code = 'personal';
    """)
    
    print("  ✓ Mapped 21 receipt categories to account codes")

def generate_report(cur):
    """Generate comprehensive report of chart of accounts."""
    print("\n4. Generating chart of accounts report...")
    
    cur.execute("""
        SELECT 
            account_code,
            account_name,
            account_type,
            qb_account_type,
            account_level,
            is_header_account,
            normal_balance,
            description
        FROM chart_of_accounts
        WHERE is_active = true
        ORDER BY account_code
    """)
    
    accounts = cur.fetchall()
    
    report = []
    report.append("\n" + "=" * 120)
    report.append("ARROW LIMOUSINE - COMPREHENSIVE CHART OF ACCOUNTS")
    report.append("=" * 120)
    report.append(f"\nTotal Accounts: {len(accounts)}\n")
    
    current_category = None
    
    for acc in accounts:
        code, name, acc_type, qb_type, level, is_header, normal_bal, description = acc
        
        # Category headers
        if level == 0:
            report.append("\n" + "=" * 120)
            report.append(f"{code} - {name.upper()}")
            report.append("=" * 120)
            current_category = name
        elif is_header and level == 1:
            report.append(f"\n{code} {name}")
            report.append("-" * 80)
        else:
            indent = "  " * level
            header_flag = " [HEADER]" if is_header else ""
            report.append(f"{indent}{code:10} {name:45} {normal_bal:6} {description[:40]}{header_flag}")
    
    report.append("\n" + "=" * 120)
    report.append("ACCOUNT TYPE SUMMARY")
    report.append("=" * 120)
    
    cur.execute("""
        SELECT 
            account_type,
            COUNT(*) as count,
            SUM(CASE WHEN is_header_account THEN 1 ELSE 0 END) as headers,
            SUM(CASE WHEN is_header_account THEN 0 ELSE 1 END) as detail_accounts
        FROM chart_of_accounts
        WHERE is_active = true
        GROUP BY account_type
        ORDER BY account_type
    """)
    
    report.append(f"\n{'Type':15} {'Total':8} {'Headers':8} {'Detail':8}")
    report.append("-" * 42)
    for row in cur.fetchall():
        report.append(f"{row[0]:15} {row[1]:8} {row[2]:8} {row[3]:8}")
    
    report_text = "\n".join(report)
    print(report_text)
    
    return report_text

def main():
    write_mode = '--write' in sys.argv
    
    if not write_mode:
        print("\n" + "=" * 100)
        print("DRY RUN - Preview of Comprehensive Chart of Accounts")
        print("=" * 100)
        print(f"\nThis will create {len(CHART_OF_ACCOUNTS)} accounts:")
        print("\nAccount Categories:")
        print("  • Assets (1000-1999): Bank accounts, A/R, fixed assets, depreciation")
        print("  • Liabilities (2000-2999): A/P, credit cards, loans, payroll taxes, GST")
        print("  • Equity (3000-3999): Owner capital, draws, retained earnings")
        print("  • Income (4000-4999): Charter revenue, gratuities, fees, interest")
        print("  • Expenses (5000-5999): Vehicle ops, payroll, office, professional, marketing, banking")
        print("\nSpecial Features:")
        print("  • Hierarchical structure (parent → child accounts)")
        print("  • QuickBooks type mapping for imports")
        print("  • Normal balance tracking (debit/credit)")
        print("  • Bank account number linking")
        print("  • Receipt category mapping")
        print("\nRun with --write to create chart of accounts")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "=" * 100)
    print("CREATING COMPREHENSIVE CHART OF ACCOUNTS")
    print("=" * 100)
    
    try:
        create_chart_of_accounts_table(cur)
        inserted, updated = populate_chart_of_accounts(cur)
        
        # Create category mapping if receipt_categories table exists
        try:
            create_category_mapping(cur)
        except Exception as e:
            print(f"  ⚠ Category mapping skipped (receipt_categories table may not exist yet)")
        
        report = generate_report(cur)
        
        conn.commit()
        
        save_progress('final_report', report)
        
        print("\n" + "=" * 100)
        print("CHART OF ACCOUNTS CREATION COMPLETE")
        print("=" * 100)
        print(f"\n✓ Total: {len(CHART_OF_ACCOUNTS)} accounts")
        print(f"✓ Inserted: {inserted} new accounts")
        print(f"✓ Updated: {updated} existing accounts")
        print("✓ Progress saved to: l:\\limo\\data\\chart_of_accounts_setup\\")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
