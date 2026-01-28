#!/usr/bin/env python3
"""
TIER 4B: Populate employee_pay_master with Calculated Pay Data
Takes calculated pay from employee_pay_calc view and populates employee_pay_master.
This is the historical record population step.
"""

import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}")
cur = conn.cursor()

print("\n" + "="*100)
print("TIER 4B: POPULATE EMPLOYEE_PAY_MASTER WITH CALCULATED DATA")
print("="*100)

# Strategy: For each employee-period combo in charter_hours_allocation view,
# INSERT into employee_pay_master with calculated values
# Mark confidence_level based on data completeness

try:
    cur.execute("""
        INSERT INTO employee_pay_master (
            employee_id, pay_period_id, fiscal_year,
            charter_hours_sum, base_pay, gratuity_amount,
            federal_tax, provincial_tax, 
            cpp_employee, ei_employee,
            gross_pay, net_pay,
            data_completeness, confidence_level, data_source, notes
        )
        SELECT
            cha.employee_id,
            cha.pay_period_id,
            pp.fiscal_year,
            cha.total_hours as charter_hours_sum,
            cha.base_pay_from_charters as base_pay,
            cha.gratuity_from_charters as gratuity_amount,
            0 as federal_tax,
            0 as provincial_tax,
            0 as cpp_employee,
            0 as ei_employee,
            (cha.base_pay_from_charters + cha.gratuity_from_charters) as gross_pay,
            (cha.base_pay_from_charters + cha.gratuity_from_charters) as net_pay,
            CASE 
                WHEN cha.total_hours > 0 THEN 95
                ELSE 50
            END as data_completeness,
            75 as confidence_level,
            'charter_hours_allocation' as data_source,
            'Base population from charter data (Tier 4B)' as notes
        FROM charter_hours_allocation cha
        JOIN pay_periods pp ON cha.pay_period_id = pp.pay_period_id
        WHERE NOT EXISTS (
            SELECT 1 FROM employee_pay_master epm
            WHERE epm.employee_id = cha.employee_id 
              AND epm.pay_period_id = cha.pay_period_id
        )
        ORDER BY cha.pay_period_id, cha.employee_id
    """)
    
    inserted_count = cur.rowcount
    conn.commit()
    
    print(f"\n✅ Inserted {inserted_count} pay records into employee_pay_master")
    
    # Verify insertion
    cur.execute("""
        SELECT 
            COUNT(DISTINCT employee_id) as employees,
            COUNT(DISTINCT pay_period_id) as periods,
            COUNT(*) as total_records,
            SUM(gross_pay) as total_gross,
            SUM(gratuity_amount) as total_gratuity,
            SUM(charter_hours_sum) as total_hours,
            AVG(data_completeness) as avg_completeness
        FROM employee_pay_master
    """)
    
    emp_count, period_count, total_records, total_gross, total_gratuity, total_hours, avg_completeness = cur.fetchone()
    
    print(f"\nPopulation Summary:")
    print("-" * 100)
    print(f"  Employees covered: {emp_count}")
    print(f"  Pay periods covered: {period_count}")
    print(f"  Total records: {total_records}")
    print(f"  Total gross pay: ${total_gross or 0:,.0f}")
    print(f"  Total gratuity: ${total_gratuity or 0:,.0f}")
    print(f"  Total hours allocated: {total_hours or 0:,.1f}")
    print(f"  Avg data completeness: {avg_completeness or 0:.0f}%")
    
    # Show sample records
    print(f"\nSample populated records (first 10):")
    print("-" * 100)
    cur.execute("""
        SELECT 
            e.name,
            pp.fiscal_year,
            pp.period_number,
            epm.charter_hours_sum,
            epm.base_pay,
            epm.gratuity_amount,
            epm.gross_pay,
            epm.data_completeness
        FROM employee_pay_master epm
        JOIN employees e ON epm.employee_id = e.employee_id
        JOIN pay_periods pp ON epm.pay_period_id = pp.pay_period_id
        WHERE epm.fiscal_year IS NOT NULL
        ORDER BY epm.fiscal_year DESC, pp.period_number DESC, e.name
        LIMIT 10
    """)
    
    print(f"{'Employee':<25} | {'Year'} | {'Period'} | {'Hours'} | {'Base Pay':<12} | {'Gratuity':<12} | {'Gross':<12} | {'Complete%'}")
    print("-" * 100)
    for row in cur.fetchall():
        if None not in row:
            name, year, period, hours, base, gratuity, gross, complete = row
            print(f"{name:<25} | {year} | {period:>6} | {hours:>5.1f} | ${base:>10,.0f} | ${gratuity:>10,.0f} | ${gross:>10,.0f} | {complete:>7.0f}%")
    
    print("\n" + "="*100)
    print("✅ TIER 4B COMPLETE - EMPLOYEE_PAY_MASTER POPULATED")
    print("="*100)
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ Error: {e}")

cur.close()
conn.close()
