#!/usr/bin/env python3
"""
TIER 4C: Apply Tax Calculations to employee_pay_master
Updates the tax columns based on 2024 Canadian tax rates for Alberta.
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}")
cur = conn.cursor()

print("\n" + "="*100)
print("TIER 4C: APPLY TAX CALCULATIONS TO EMPLOYEE_PAY_MASTER")
print("="*100)

# 2024 Canadian Tax Rates
# Federal (progressive: 15%, 20.5%, 26%, 29%, 33%)
#   $0 - $55,867: 15%
#   $55,867 - $111,733: 20.5% 
#   $111,733 - $173,205: 26%
#   $173,205 - $246,752: 29%
#   $246,752+: 33%
#
# Alberta Provincial (progressive: 10%, 12%, 13%, 14%, 15%)
#   $0 - $148,269: 10%
#   $148,269 - $177,922: 12%
#   $177,922 - $237,230: 13%
#   $237,230 - $355,845: 14%
#   $355,845+: 15%
#
# CPP (5.95% of pensionable earnings between $3,500 and $68,500)
# EI (1.64% of insurable earnings up to $63,200 max annual)

try:
    # Calculate and update tax columns using SQL function approach
    cur.execute("""
        UPDATE employee_pay_master epm
        SET 
            federal_tax = CASE
                WHEN gross_pay <= 55867 THEN gross_pay * 0.15
                WHEN gross_pay <= 111733 THEN 55867 * 0.15 + (gross_pay - 55867) * 0.205
                WHEN gross_pay <= 173205 THEN 55867 * 0.15 + (111733 - 55867) * 0.205 + (gross_pay - 111733) * 0.26
                WHEN gross_pay <= 246752 THEN 55867 * 0.15 + (111733 - 55867) * 0.205 + (173205 - 111733) * 0.26 + (gross_pay - 173205) * 0.29
                ELSE 55867 * 0.15 + (111733 - 55867) * 0.205 + (173205 - 111733) * 0.26 + (246752 - 173205) * 0.29 + (gross_pay - 246752) * 0.33
            END,
            provincial_tax = CASE
                WHEN gross_pay <= 148269 THEN gross_pay * 0.10
                WHEN gross_pay <= 177922 THEN 148269 * 0.10 + (gross_pay - 148269) * 0.12
                WHEN gross_pay <= 237230 THEN 148269 * 0.10 + (177922 - 148269) * 0.12 + (gross_pay - 177922) * 0.13
                WHEN gross_pay <= 355845 THEN 148269 * 0.10 + (177922 - 148269) * 0.12 + (237230 - 177922) * 0.13 + (gross_pay - 237230) * 0.14
                ELSE 148269 * 0.10 + (177922 - 148269) * 0.12 + (237230 - 177922) * 0.13 + (355845 - 237230) * 0.14 + (gross_pay - 355845) * 0.15
            END,
            cpp_employee = CASE
                WHEN charter_hours_sum > 0 AND gross_pay > 3500 THEN LEAST((gross_pay - 3500) * 0.0595, (68500 - 3500) * 0.0595)
                ELSE 0
            END,
            ei_employee = CASE
                WHEN charter_hours_sum > 0 THEN LEAST(gross_pay * 0.0164, 63200 * 0.0164)
                ELSE 0
            END,
            total_deductions = COALESCE(federal_tax, 0) + COALESCE(provincial_tax, 0) + 
                              COALESCE(cpp_employee, 0) + COALESCE(ei_employee, 0) +
                              COALESCE(union_dues, 0) + COALESCE(radio_dues, 0) + 
                              COALESCE(voucher_deductions, 0) + COALESCE(misc_deductions, 0),
            net_pay = GREATEST(0, gross_pay - 
                              COALESCE(federal_tax, 0) - COALESCE(provincial_tax, 0) - 
                              COALESCE(cpp_employee, 0) - COALESCE(ei_employee, 0) -
                              COALESCE(union_dues, 0) - COALESCE(radio_dues, 0) - 
                              COALESCE(voucher_deductions, 0) - COALESCE(misc_deductions, 0))
        WHERE federal_tax = 0 OR federal_tax IS NULL
    """)
    
    updated_count = cur.rowcount
    conn.commit()
    
    print(f"\n✅ Updated {updated_count} employee_pay_master records with tax calculations")
    
    # Verify calculation
    cur.execute("""
        SELECT 
            SUM(COALESCE(federal_tax, 0)) as total_federal,
            SUM(COALESCE(provincial_tax, 0)) as total_provincial,
            SUM(COALESCE(cpp_employee, 0)) as total_cpp,
            SUM(COALESCE(ei_employee, 0)) as total_ei,
            SUM(COALESCE(total_deductions, 0)) as total_deductions,
            SUM(COALESCE(net_pay, 0)) as total_net,
            SUM(COALESCE(gross_pay, 0)) as total_gross,
            AVG(CASE WHEN gross_pay > 0 THEN (federal_tax + provincial_tax) / gross_pay * 100 ELSE 0 END) as avg_tax_rate_pct
        FROM employee_pay_master
        WHERE fiscal_year IS NOT NULL
    """)
    
    fed, prov, cpp, ei, total_ded, net, gross, avg_tax_rate = cur.fetchone()
    
    print(f"\nTax Calculation Verification:")
    print("-" * 100)
    print(f"  Total Gross Pay: ${gross or 0:,.0f}")
    print(f"  Federal Income Tax: ${fed or 0:,.0f}")
    print(f"  Provincial Income Tax: ${prov or 0:,.0f}")
    print(f"  CPP Contributions: ${cpp or 0:,.0f}")
    print(f"  EI Contributions: ${ei or 0:,.0f}")
    print(f"  Total Deductions: ${total_ded or 0:,.0f}")
    print(f"  Net Pay Calculated: ${net or 0:,.0f}")
    print(f"  Average Effective Tax Rate: {avg_tax_rate or 0:.1f}%")
    
    # Show sample calculations
    print(f"\nSample Tax Calculations (top 10 earners):")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            e.name,
            SUM(epm.gross_pay) as total_gross,
            SUM(epm.federal_tax) as total_fed,
            SUM(epm.provincial_tax) as total_prov,
            SUM(epm.cpp_employee) as total_cpp,
            SUM(epm.ei_employee) as total_ei,
            SUM(epm.net_pay) as total_net,
            ROUND(100.0 * (SUM(epm.federal_tax) + SUM(epm.provincial_tax)) / NULLIF(SUM(epm.gross_pay), 0), 1) as effective_tax_rate
        FROM employee_pay_master epm
        JOIN employees e ON epm.employee_id = e.employee_id
        WHERE epm.fiscal_year = 2024
        GROUP BY e.employee_id, e.name
        ORDER BY total_gross DESC
        LIMIT 10
    """)
    
    print(f"{'Employee':<25} | {'Gross':<12} | {'Federal':<10} | {'Prov':<10} | {'CPP':<8} | {'EI':<8} | {'Net':<12} | {'Tax %'}")
    print("-" * 100)
    
    for name, gross, fed, prov, cpp, ei, net, tax_rate in cur.fetchall():
        gross = gross or 0
        fed = fed or 0
        prov = prov or 0
        cpp = cpp or 0
        ei = ei or 0
        net = net or 0
        tax_rate = tax_rate or 0
        print(f"{name:<25} | ${gross:>10,.0f} | ${fed:>8,.0f} | ${prov:>8,.0f} | ${cpp:>6,.0f} | ${ei:>6,.0f} | ${net:>10,.0f} | {tax_rate:>5.1f}%")
    
    print("\n" + "="*100)
    print("✅ TIER 4C COMPLETE - TAX CALCULATIONS APPLIED")
    print("="*100)
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

cur.close()
conn.close()
