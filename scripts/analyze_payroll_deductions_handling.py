#!/usr/bin/env python3
"""
Comprehensive analysis of how pay contributions, deductions, T4, WCB, and ROE
are handled in the codebase.
"""

import os
import psycopg2
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("="*80)
print("PAYROLL DEDUCTIONS, CONTRIBUTIONS & TAX HANDLING")
print("="*80)

# 1. Driver Payroll Structure
print("\n" + "="*80)
print("1. DRIVER PAYROLL TABLE STRUCTURE (16,370 records)")
print("="*80)

print("\nCore Financial Fields:")
print("  gross_pay        - DECIMAL(12,2) - Total gross pay")
print("  base_wages       - DECIMAL(12,2) - Base pay (explicit)")
print("  gratuity_amount  - DECIMAL(12,2) - Gratuities earned")
print("  expense_reimbursement - DECIMAL(12,2) - Reimbursable expenses")

print("\nDeductions (Employee's portion):")
print("  cpp              - DECIMAL(12,2) - CPP (Canada Pension Plan) deduction")
print("  ei               - DECIMAL(12,2) - EI (Employment Insurance) deduction")
print("  tax              - DECIMAL(12,2) - Income tax withheld")
print("  total_deductions - DECIMAL(12,2) - Sum of all deductions")

print("\nWCB (Workers' Compensation Board):")
print("  wcb_payment      - DECIMAL(12,2) - WCB premium paid (EMPLOYER cost)")
print("  wcb_rate         - DECIMAL(10,4) - WCB rate per $100 of payroll")

print("\nT4 Information (stored in T4_box_XX columns):")
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'driver_payroll'
    AND column_name LIKE 't4_box_%'
    ORDER BY column_name
""")
t4_columns = cur.fetchall()
for col, dtype in t4_columns:
    print(f"  {col:<25} - T4 Box mapping")

print("\n" + "="*80)
print("2. HOW DEDUCTIONS ARE CALCULATED")
print("="*80)

print("\nFrom create_sqlite_payroll_staging.py & import_payroll_wcb.py:")
print("\n✅ CPP (Canada Pension Plan):")
print("   - Parsed from payroll files as: 'cpp - employee' (employee contribution)")
print("   - Also tracked: 'cpp - company' (employer contribution)")
print("   - Stored in driver_payroll.cpp (employee portion)")
print("   - Maximum contribution: ~$3,500/year (2024)")

print("\n✅ EI (Employment Insurance):")
print("   - Parsed from payroll files as: 'ei - employee' (employee contribution)")
print("   - Also tracked: 'ei - company' (employer contribution)")
print("   - Stored in driver_payroll.ei (employee portion)")
print("   - Employee rate: ~1.62% of insurable earnings (Alberta)")

print("\n✅ Income Tax:")
print("   - Parsed as: 'federal income tax', 'provincial income tax'")
print("   - Stored in driver_payroll.tax (combined)")
print("   - Based on T4 exemptions in employees table")

print("\n✅ Total Deductions:")
print("   - Calculated as: cpp + ei + tax + other_deductions")
print("   - Net Pay = Gross Pay - Total Deductions")

# 2. T4 Information
print("\n" + "="*80)
print("3. T4 (TAX FORM) HANDLING")
print("="*80)

cur.execute("""
    SELECT fiscal_year, COUNT(*) as count, 
           SUM(t4_employment_income) as total_income,
           SUM(t4_federal_tax) as federal_tax,
           SUM(t4_provincial_tax) as prov_tax
    FROM employee_t4_summary
    GROUP BY fiscal_year
    ORDER BY fiscal_year DESC
    LIMIT 5
""")

print("\nT4 Summary Data (employee_t4_summary):")
print(f"{'Year':<8} {'Employees':<12} {'Total Income':<18} {'Federal Tax':<18} {'Prov Tax':<18}")
print("-"*80)
for row in cur.fetchall():
    year, count, income, fed_tax, prov_tax = row
    income_str = f"${float(income or 0):,.2f}" if income else "$0.00"
    fed_str = f"${float(fed_tax or 0):,.2f}" if fed_tax else "$0.00"
    prov_str = f"${float(prov_tax or 0):,.2f}" if prov_tax else "$0.00"
    print(f"{year:<8} {count:<12} {income_str:<18} {fed_str:<18} {prov_str:<18}")

print("\nT4 Box Mappings:")
print("  Box 14  - Employment Income (gross pay)")
print("  Box 16  - CPP Contribution ($)")
print("  Box 18  - EI Contribution ($)")
print("  Box 22  - Income Tax Withheld ($)")
print("  Box 24  - EI Insurable Earnings")
print("  Box 26  - Union Dues")
print("  Box 44  - Deferred Income Plan (pension)")
print("  Box 46  - Deferred Income - amount deferred")
print("  Box 52  - CPP/QPP Contribution (employer)")

# 3. ROE Information
print("\n" + "="*80)
print("4. ROE (RECORD OF EMPLOYMENT) HANDLING")
print("="*80)

cur.execute("SELECT COUNT(*) FROM employee_roe_records")
roe_count = cur.fetchone()[0]

cur.execute("""
    SELECT employee_name, reason_code, COUNT(*) as count
    FROM employee_roe_records
    GROUP BY employee_name, reason_code
    ORDER BY employee_name
""")

print(f"\nROE Records: {roe_count} records")
if roe_count > 0:
    print(f"\n{'Employee':<20} {'Reason Code':<15} {'Count':<5}")
    print("-"*50)
    for row in cur.fetchall():
        name, reason, count = row
        print(f"{name:<20} {reason or 'N/A':<15} {count:<5}")

# 4. WCB Information
print("\n" + "="*80)
print("5. WCB (WORKERS' COMPENSATION) HANDLING")
print("="*80)

print("\nWCB in driver_payroll:")
print("  wcb_payment     - Amount paid to WCB (employer cost)")
print("  wcb_rate        - Rate per $100 of payroll (0.35-2.50 depending on risk)")

cur.execute("""
    SELECT 
        COUNT(*) as records,
        SUM(wcb_payment) as total_wcb,
        AVG(wcb_rate) as avg_rate,
        MIN(wcb_rate) as min_rate,
        MAX(wcb_rate) as max_rate
    FROM driver_payroll
    WHERE wcb_payment > 0 OR wcb_rate > 0
""")

row = cur.fetchone()
if row and row[0] and row[0] > 0:
    count, total, avg_rate, min_rate, max_rate = row
    print(f"\nWCB Data Summary:")
    print(f"  Records with WCB: {count:,}")
    print(f"  Total WCB paid:   ${float(total or 0):,.2f}")
    print(f"  Average rate:     {float(avg_rate or 0):.4f}/\$100")
    print(f"  Rate range:       {float(min_rate or 0):.4f} - {float(max_rate or 0):.4f}/\$100")
else:
    print("\n⚠️  No WCB payment data in driver_payroll table")

# 5. Employee Pay Master
print("\n" + "="*80)
print("6. EMPLOYEE PAY MASTER TABLE (2,653 records)")
print("="*80)

print("\nComprehensive payroll breakdown structure:")
print("  base_pay         - Regular pay calculation")
print("  gratuity_percent - Gratuity % applied")
print("  gratuity_amount  - Calculated gratuity")
print("  overtime_hours   - OT calculation field")
print("  federal_tax      - Federal income tax")
print("  provincial_tax   - Provincial income tax")
print("  cpp_employee     - CPP (employee portion)")
print("  ei_employee      - EI (employee portion)")
print("  union_dues       - Union dues deduction")
print("  radio_dues       - Radio equipment dues")
print("  voucher_deductions - Voucher/loan deductions")
print("  misc_deductions  - Other deductions")
print("  total_deductions - Sum of all deductions")
print("  net_pay          - Gross - Deductions")

cur.execute("""
    SELECT 
        COUNT(*) as records,
        SUM(gross_pay) as total_gross,
        SUM(cpp_employee) as total_cpp,
        SUM(ei_employee) as total_ei,
        SUM(federal_tax + provincial_tax) as total_tax,
        SUM(net_pay) as total_net
    FROM employee_pay_master
""")

row = cur.fetchone()
if row:
    count, gross, cpp, ei, tax, net = row
    print(f"\nEmployee Pay Master Totals:")
    print(f"  Records:     {count:,}")
    print(f"  Gross Pay:   ${float(gross or 0):,.2f}")
    print(f"  CPP:         ${float(cpp or 0):,.2f}")
    print(f"  EI:          ${float(ei or 0):,.2f}")
    print(f"  Income Tax:  ${float(tax or 0):,.2f}")
    print(f"  Net Pay:     ${float(net or 0):,.2f}")

# 6. Payment Methods
print("\n" + "="*80)
print("7. HOW PAYMENT DATA IS STORED")
print("="*80)

print("\nPayroll Flow:")
print("  1. driver_payroll (16,370) - Transaction-level pay records")
print("  2. employee_pay_master (2,653) - Aggregated by employee/period")
print("  3. employee_t4_summary (17) - Year-end T4 data by employee")
print("  4. payments table (28,998) - Actual payment records")
print("  5. receipts table - WCB payments as expense receipts")

print("\nPayment Flows:")
print("  ✅ Driver salary → driver_payroll → payments table")
print("  ✅ Employee salary → employee_pay_master → payments table")
print("  ✅ WCB fees → wcb_payment in driver_payroll → receipts table")
print("  ✅ T4 boxes → employee_t4_summary (reference only)")

# 7. Payroll Adjustments
print("\n" + "="*80)
print("8. PAYROLL ADJUSTMENTS & CORRECTIONS")
print("="*80)

cur.execute("SELECT COUNT(*) FROM payroll_adjustments")
adj_count = cur.fetchone()[0]

print(f"\nPayroll Adjustments Table: {adj_count} records")
if adj_count > 0:
    cur.execute("""
        SELECT adjustment_type, COUNT(*) as count, 
               SUM(gross_amount) as total
        FROM payroll_adjustments
        GROUP BY adjustment_type
    """)
    print(f"\n{'Adjustment Type':<30} {'Count':<10} {'Total Amount':<15}")
    print("-"*60)
    for row in cur.fetchall():
        adj_type, count, total = row
        print(f"{adj_type:<30} {count:<10} ${float(total or 0):>12,.2f}")

# 8. Data Quality
print("\n" + "="*80)
print("9. DATA QUALITY & VALIDATION ISSUES")
print("="*80)

print("\nKnown Issues with T4/Deduction Data:")
print("  ⚠️  T4 data incomplete (17 records for multiple years)")
print("  ⚠️  WCB payment tracking inconsistent across records")
print("  ⚠️  Some deductions not explicitly stored (split across multiple fields)")
print("  ⚠️  No automatic validation of CPP/EI calculation correctness")
print("  ⚠️  ROE records sparse (only 2 records)")

# 9. Missing Implementation
print("\n" + "="*80)
print("10. WHAT'S NOT CURRENTLY IMPLEMENTED")
print("="*80)

print("\n❌ Missing Implementation:")
print("  1. Automatic CPP/EI rate validation against CRA limits")
print("  2. Automatic provincial tax calculation")
print("  3. Vacation pay accrual tracking (only 3 records)")
print("  4. Sick leave / personal days")
print("  5. Direct deposit automation")
print("  6. CRA HST/GST tracking for wages (if applicable)")
print("  7. Pension/RRSP deduction management")
print("  8. Wage recovery/garnishment tracking")
print("  9. Parental leave benefits")
print("  10. Casual vs permanent classification (stored but not used in calc)")

print("\n" + "="*80)
print("SUMMARY: How the System Currently Works")
print("="*80)

print("""
DEDUCTION FLOW:
1. Parse payroll files (Excel/PDF) for CPP, EI, TAX amounts
2. Store in driver_payroll.cpp, driver_payroll.ei, driver_payroll.tax
3. Calculate: total_deductions = cpp + ei + tax + other
4. Calculate: net_pay = gross_pay - total_deductions
5. Reference T4 data in employee_t4_summary (mostly read-only)

CONTRIBUTIONS CALCULATION:
- CPP: ~5.95% for employee (~5.95% employer match) - CAPPED at $3,867.50/year
- EI: ~1.62% for employee (~1.82% employer match) - CAPPED at insurable earnings limit
- WCB: Percentage of payroll (0.35%-2.50%) per province/industry

T4 HANDLING:
- employee_t4_summary stores year-end totals by box
- Boxes 14, 16, 18, 22, 24 are key fields for CRA reporting
- Data is mostly imported, not calculated

ROE (RECORD OF EMPLOYMENT):
- Minimal implementation (only 2 records)
- Reason codes: A (Voluntary Quit?), R (Recall?)
- Used for EI claims but not actively generated

WEAKNESSES:
1. Calculations are "pass-through" (stored as-is from imports)
2. No validation against CRA limits and requirements
3. T4 data not auto-generated from driver_payroll
4. WCB tracking spotty and incomplete
5. No deferred wage tracking despite "deferred_wage_*" tables existing
6. Payroll fixes are manual (payroll_fix_audit table tracks them)
""")

cur.close()
conn.close()
