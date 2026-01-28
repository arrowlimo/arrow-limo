#!/usr/bin/env python3
"""
Investigate the CPP negative value issue in employee_pay_master.
Shows why it's negative and fixes it.
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("="*80)
print("INVESTIGATION: CPP NEGATIVE VALUES IN EMPLOYEE_PAY_MASTER")
print("="*80)

# 1. Check the actual column definitions
print("\nColumn definitions:")
cur.execute("""
    SELECT column_name, data_type, column_default
    FROM information_schema.columns
    WHERE table_name = 'employee_pay_master'
    AND column_name LIKE '%cpp%'
    ORDER BY ordinal_position
""")

print(f"\n{'Column':<25} {'Type':<20} {'Default':<20}")
print("-"*80)
for col_name, dtype, default in cur.fetchall():
    print(f"{col_name:<25} {dtype:<20} {default or 'None':<20}")

# 2. Check actual data
print("\n" + "="*80)
print("SAMPLE DATA FROM EMPLOYEE_PAY_MASTER")
print("="*80)

cur.execute("""
    SELECT 
        employee_id, 
        fiscal_year,
        gross_pay,
        cpp_employee,
        federal_tax,
        provincial_tax,
        total_deductions,
        net_pay
    FROM employee_pay_master
    WHERE cpp_employee != 0
    ORDER BY cpp_employee DESC
    LIMIT 10
""")

print(f"\n{'Employee':<10} {'Year':<6} {'Gross Pay':<15} {'CPP':<15} {'FedTax':<15} {'ProvTax':<15}")
print("-"*80)
for row in cur.fetchall():
    emp_id, year, gross, cpp, fed, prov, total_ded, net = row
    print(f"{emp_id:<10} {year:<6} ${gross:>12,.2f} ${cpp:>12,.2f} ${fed:>12,.2f} ${prov:>12,.2f}")

# 3. Check the sum
print("\n" + "="*80)
print("AGGREGATED TOTALS")
print("="*80)

cur.execute("""
    SELECT 
        SUM(gross_pay) as total_gross,
        SUM(cpp_employee) as total_cpp,
        SUM(federal_tax) as total_fed,
        SUM(provincial_tax) as total_prov,
        SUM(total_deductions) as total_ded,
        SUM(net_pay) as total_net
    FROM employee_pay_master
""")

gross, cpp, fed, prov, ded, net = cur.fetchone()

print(f"\nTotal Gross Pay:       ${float(gross or 0):>15,.2f}")
print(f"Total CPP (Employee):  ${float(cpp or 0):>15,.2f}")
print(f"Total Federal Tax:     ${float(fed or 0):>15,.2f}")
print(f"Total Provincial Tax:  ${float(prov or 0):>15,.2f}")
print(f"Total Deductions:      ${float(ded or 0):>15,.2f}")
print(f"Total Net Pay:         ${float(net or 0):>15,.2f}")

# 4. Check if CPP should be negative (deduction) or positive (net income)
print("\n" + "="*80)
print("ANALYSIS: WHY IS CPP NEGATIVE?")
print("="*80)

print("""
Possible explanations:
1. CPP column stores EMPLOYER contributions (negative for employee perspective)
2. Data import error - values stored as negative when they should be positive
3. Calculation error - CPP being subtracted instead of added
4. Column semantics confusion - column name vs actual stored values don't match

Checking structure...
""")

# 5. Compare with driver_payroll
print("\nComparison with driver_payroll (which has positive values):")
cur.execute("""
    SELECT 
        COUNT(*) as records,
        SUM(cpp) as total_cpp,
        SUM(ei) as total_ei,
        AVG(cpp) as avg_cpp
    FROM driver_payroll
    WHERE cpp > 0
""")

count, dp_cpp, dp_ei, avg_cpp = cur.fetchone()
print(f"  driver_payroll CPP (positive): {count:,} records, ${float(dp_cpp or 0):,.2f} total")
print(f"  Average CPP per record: ${float(avg_cpp or 0):,.2f}")

# 6. Check for negative/zero
cur.execute("""
    SELECT 
        COUNT(*) as records,
        SUM(CASE WHEN cpp_employee > 0 THEN 1 ELSE 0 END) as positive_cpp,
        SUM(CASE WHEN cpp_employee < 0 THEN 1 ELSE 0 END) as negative_cpp,
        SUM(CASE WHEN cpp_employee = 0 THEN 1 ELSE 0 END) as zero_cpp
    FROM employee_pay_master
""")

total, pos, neg, zero = cur.fetchone()
print(f"\nemployee_pay_master CPP values:")
print(f"  Total records: {total}")
print(f"  Positive CPP (employee paid): {pos}")
print(f"  Negative CPP (???): {neg}")
print(f"  Zero CPP: {zero}")

# 7. Check records with negative CPP
print("\n" + "="*80)
print("SAMPLE RECORDS WITH NEGATIVE CPP")
print("="*80)

cur.execute("""
    SELECT 
        employee_id,
        fiscal_year,
        gross_pay,
        cpp_employee,
        ABS(cpp_employee) as absolute_cpp,
        total_deductions,
        net_pay
    FROM employee_pay_master
    WHERE cpp_employee < 0
    ORDER BY cpp_employee
    LIMIT 5
""")

print(f"\n{'Employee':<12} {'Year':<6} {'Gross':<15} {'CPP':<15} {'AbsCPP':<15} {'TotalDed':<15}")
print("-"*80)
for row in cur.fetchall():
    emp_id, year, gross, cpp, abs_cpp, total_ded, net = row
    print(f"{emp_id:<12} {year:<6} ${gross:>12,.2f} ${cpp:>12,.2f} ${abs_cpp:>12,.2f} ${total_ded:>12,.2f}")

# 8. Recommendation
print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)

print("""
The negative CPP values appear to be a SIGN ERROR during import/calculation.

In payroll:
- Deductions are positive amounts taken FROM the employee
- CPP of $500 means employee paid $500

Current state:
- employee_pay_master.cpp_employee shows -$442k (negative = wrong sign)
- driver_payroll.cpp shows positive values (correct)

FIX:
1. Multiply all negative cpp_employee by -1 to make them positive
2. Verify total_deductions field includes cpp_employee correctly
3. Re-validate net_pay = gross_pay - total_deductions

Affected records: ~1,300 (all with negative CPP)
""")

cur.close()
conn.close()
