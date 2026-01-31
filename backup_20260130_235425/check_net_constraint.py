#!/usr/bin/env python3
"""
Check the CHECK constraint on employee_pay_master and see what's causing the violation.
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
print("CHECK CONSTRAINT INVESTIGATION")
print("="*80)

# Get constraint details
cur.execute("""
    SELECT constraint_name, check_clause
    FROM information_schema.check_constraints
    WHERE constraint_name LIKE '%check%'
    ORDER BY constraint_name
""")

print("\nCHECK Constraints on employee_pay_master:")
print("-"*80)
for constraint_name, check_clause in cur.fetchall():
    print(f"{constraint_name}: {check_clause}")

# Check what the problematic records are
print("\n" + "="*80)
print("RECORDS THAT VIOLATE CHECK CONSTRAINT")
print("="*80)

cur.execute("""
    SELECT 
        employee_pay_id,
        employee_id,
        gross_pay,
        total_deductions,
        net_pay
    FROM employee_pay_master
    WHERE net_pay < 0
    ORDER BY net_pay
    LIMIT 10
""")

print(f"\n{'ID':<8} {'Employee':<12} {'Gross':<15} {'Deductions':<15} {'Net':<15}")
print("-"*80)
for row in cur.fetchall():
    pay_id, emp_id, gross, ded, net = row
    print(f"{pay_id:<8} {emp_id:<12} ${gross:>12,.2f} ${ded:>12,.2f} ${net:>12,.2f}")

# Count violations
cur.execute("""
    SELECT COUNT(*) FROM employee_pay_master WHERE net_pay < 0
""")

neg_count = cur.fetchone()[0]

print(f"\nTotal records with negative net_pay: {neg_count}")

if neg_count > 0:
    print(f"\n⚠️  These records have INVALID payroll data:")
    print(f"   - Total deductions exceed gross pay")
    print(f"   - This suggests data quality issues in source files")
    print(f"   - Options:")
    print(f"     1. Cap deductions at gross pay")
    print(f"     2. Flag records as requiring manual review")
    print(f"     3. Check source documents for errors")

cur.close()
conn.close()
