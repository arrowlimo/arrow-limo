#!/usr/bin/env python
"""TIER 2B: Create employee_pay_calc_view - comprehensive pay calculation engine.
Calculates: hours × rate + gratuity + reimbursements - deductions = net pay
"""
import psycopg2
import os

DB_HOST=os.environ.get("DB_HOST","localhost")
DB_NAME=os.environ.get("DB_NAME","almsdata")
DB_USER=os.environ.get("DB_USER","postgres")
DB_PASSWORD=os.environ.get("DB_PASSWORD","***REMOVED***")

conn=psycopg2.connect(host=DB_HOST,database=DB_NAME,user=DB_USER,password=DB_PASSWORD)
cur=conn.cursor()

print("\n"+"="*100)
print("TIER 2B: CREATE EMPLOYEE_PAY_CALC VIEW (PAY CALCULATION ENGINE)")
print("="*100)
print()

# Drop if exists
cur.execute("DROP VIEW IF EXISTS employee_pay_calc CASCADE")
print("✅ Dropped existing view")

# Create comprehensive pay calculation view
cur.execute("""
    CREATE VIEW employee_pay_calc AS
    SELECT 
        -- IDs & Period
        COALESCE(cha.employee_id, e.employee_id) as employee_id,
        pp.pay_period_id,
        pp.fiscal_year,
        pp.period_number,
        pp.period_start_date,
        pp.period_end_date,
        pp.pay_date,
        
        -- Employee info
        e.full_name,
        e.hourly_rate,
        
        -- Hours (from charters)
        COALESCE(cha.trip_count, 0) as trip_count,
        COALESCE(cha.total_hours, 0) as charter_hours,
        COALESCE(cha.distinct_days_worked, 0) as days_worked,
        
        -- Base pay calculation
        COALESCE(cha.total_hours * e.hourly_rate, 0) as calculated_base_pay,
        COALESCE(cha.base_pay_from_charters, 0) as charter_base_pay,
        
        -- Gratuity (if applicable)
        COALESCE(cha.gratuity_from_charters, 0) as gratuity_collected,
        
        -- Income components (gross)
        COALESCE(cha.total_hours * e.hourly_rate, 0) 
            + COALESCE(cha.gratuity_from_charters, 0) as gross_income_before_deductions,
        
        -- Tax calculation (simplified - based on gross)
        -- Federal: Use basic tax calculation (15% for lowest bracket, simplified)
        CASE 
            WHEN COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 < 15705 THEN 0  -- Below exemption
            WHEN COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 < 31560 THEN 
                (COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 - 15705) * 0.15 / 26
            ELSE 
                ((COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 - 31560) * 0.205 + (31560-15705) * 0.15) / 26
        END as federal_tax_calc,
        
        -- Provincial (Alberta): 10% for most
        CASE 
            WHEN COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 < 14156 THEN 0
            WHEN COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 < 28311 THEN 
                (COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 - 14156) * 0.10 / 26
            ELSE 
                ((COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 - 28311) * 0.12 + (28311-14156) * 0.10) / 26
        END as provincial_tax_calc,
        
        -- CPP (5.95% on earnings between $3,500 and $68,500 annually, ~$11.40/week average)
        CASE 
            WHEN COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 < 3500 THEN 0
            WHEN COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 > 68500 THEN (68500 - 3500) * 0.0595 / 26
            ELSE (COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 - 3500) * 0.0595 / 26
        END as cpp_employee_calc,
        
        -- EI (1.64% on earnings up to $63,200 annually)
        CASE 
            WHEN COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 > 63200 THEN 63200 * 0.0164 / 26
            ELSE COALESCE(cha.total_hours * e.hourly_rate, 0) * 0.0164
        END as ei_employee_calc,
        
        -- Union/radio dues (from employee master)
        COALESCE(e.deduction_radio_dues, 0) as radio_dues,
        
        -- Total deductions
        COALESCE(cha.total_hours * e.hourly_rate, 0)
            + COALESCE(cha.gratuity_from_charters, 0)
            - (CASE WHEN COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 < 15705 THEN 0 
                    WHEN COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 < 31560 THEN 
                        (COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 - 15705) * 0.15 / 26
                    ELSE ((COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 - 31560) * 0.205 + (31560-15705) * 0.15) / 26
               END)
            - (CASE WHEN COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 < 14156 THEN 0
                    WHEN COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 < 28311 THEN 
                        (COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 - 14156) * 0.10 / 26
                    ELSE ((COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 - 28311) * 0.12 + (28311-14156) * 0.10) / 26
               END)
            - (CASE WHEN COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 < 3500 THEN 0
                    WHEN COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 > 68500 THEN (68500 - 3500) * 0.0595 / 26
                    ELSE (COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 - 3500) * 0.0595 / 26
               END)
            - (CASE WHEN COALESCE(cha.total_hours * e.hourly_rate, 0) * 26 > 63200 THEN 63200 * 0.0164 / 26
                    ELSE COALESCE(cha.total_hours * e.hourly_rate, 0) * 0.0164
               END)
            - COALESCE(e.deduction_radio_dues, 0) as net_pay_calculated,
        
        -- Data quality
        CASE 
            WHEN COALESCE(cha.trip_count, 0) = 0 THEN 0
            WHEN COALESCE(cha.trip_count, 0) > 0 AND COALESCE(cha.total_hours, 0) > 0 THEN 100
            ELSE 50
        END as data_completeness
    FROM pay_periods pp
    LEFT JOIN employees e ON true
    LEFT JOIN charter_hours_allocation cha ON cha.pay_period_id = pp.pay_period_id
    WHERE e.is_chauffeur = true AND e.employment_status != 'terminated'
""")
print("✅ Created employee_pay_calc view")

# Show sample calculations
print("\nSample 2024-Q1 Pay Calculations:")
print("-" * 100)
cur.execute("""
    SELECT 
        full_name,
        period_number,
        charter_hours,
        hourly_rate,
        gross_income_before_deductions,
        federal_tax_calc,
        provincial_tax_calc,
        cpp_employee_calc,
        ei_employee_calc,
        net_pay_calculated
    FROM employee_pay_calc
    WHERE fiscal_year = 2024 AND period_number <= 2 AND charter_hours > 0
    ORDER BY period_number, full_name
    LIMIT 15
""")
print("Employee | Period | Hours | Rate | Gross | Fed Tax | Prov Tax | CPP | EI | Net Pay")
print("-" * 100)
for name, period, hours, rate, gross, fed, prov, cpp, ei, net in cur.fetchall():
    hours = hours or 0
    rate = rate or 0
    gross = gross or 0
    fed = fed or 0
    prov = prov or 0
    cpp = cpp or 0
    ei = ei or 0
    net = net or 0
    print(f"{name:<20} | {period} | {hours:>6.1f} | ${rate:>5.2f} | ${gross:>8,.0f} | ${fed:>6,.0f} | ${prov:>6,.0f} | ${cpp:>4,.0f} | ${ei:>4,.0f} | ${net:>8,.0f}")

# Annual summary for 2024
print("\n2024 Annual Pay Summary (All Drivers):")
print("-" * 100)
cur.execute("""
    SELECT 
        COUNT(DISTINCT employee_id) as employees,
        SUM(charter_hours) as total_hours,
        SUM(gross_income_before_deductions) as total_gross,
        SUM(federal_tax_calc) as total_federal_tax,
        SUM(provincial_tax_calc) as total_provincial_tax,
        SUM(cpp_employee_calc) as total_cpp,
        SUM(ei_employee_calc) as total_ei,
        SUM(net_pay_calculated) as total_net
    FROM employee_pay_calc
    WHERE fiscal_year = 2024
""")
emp_cnt, tot_hrs, tot_gross, tot_fed, tot_prov, tot_cpp, tot_ei, tot_net = cur.fetchone()
print(f"Employees: {emp_cnt}")
print(f"Total hours: {tot_hrs:,.1f}")
print(f"Total gross: ${tot_gross:,.2f}")
print(f"  - Federal tax: ${tot_fed:,.2f}")
print(f"  - Provincial tax: ${tot_prov:,.2f}")
print(f"  - CPP: ${tot_cpp:,.2f}")
print(f"  - EI: ${tot_ei:,.2f}")
print(f"Total net (calculated): ${tot_net:,.2f}")

conn.commit()
cur.close()
conn.close()

print("\n✅ TIER 2B COMPLETE - PAY CALCULATION ENGINE CREATED!")
print()
print("Next: TIER 2C - Tax deduction calculator & Tier 3 - T4 reconciliation")
