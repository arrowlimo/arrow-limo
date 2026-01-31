#!/usr/bin/env python3
"""
Check which records WOULD violate check_net if we fix CPP negative values.
This simulates: fix_cpp_employee = ABS(cpp_employee), and recalc net_pay = gross - deductions
"""

import os
import psycopg2
from decimal import Decimal

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

print("="*100)
print("SIMULATION: CPP FIX - WHICH RECORDS WOULD VIOLATE CHECK_NET?")
print("="*100)

# Get all records where we'd make a change
cur.execute("""
    SELECT 
        employee_pay_id,
        employee_id,
        gross_pay,
        cpp_employee,
        ei_employee,
        federal_tax,
        provincial_tax,
        total_deductions,
        net_pay
    FROM employee_pay_master
    WHERE cpp_employee < 0
    ORDER BY net_pay DESC
""")

records = cur.fetchall()
print(f"\nTotal records with negative cpp_employee: {len(records)}")

problematic = []

for row in records:
    pay_id, emp_id, gross, cpp, ei, fed_tax, prov_tax, ded, net = row
    gross = Decimal(str(gross)) if gross else Decimal(0)
    cpp = Decimal(str(cpp)) if cpp else Decimal(0)
    ei = Decimal(str(ei)) if ei else Decimal(0)
    fed_tax = Decimal(str(fed_tax)) if fed_tax else Decimal(0)
    prov_tax = Decimal(str(prov_tax)) if prov_tax else Decimal(0)
    ded = Decimal(str(ded)) if ded else Decimal(0)
    net = Decimal(str(net)) if net else Decimal(0)
    
    # Simulate the fix
    fixed_cpp = abs(cpp)  # Flip sign
    fixed_total_ded = (ded - cpp) + fixed_cpp  # Remove old cpp, add fixed cpp
    fixed_net = gross - fixed_total_ded
    
    # Check if would violate constraint
    if fixed_net < 0:
        problematic.append({
            'id': pay_id,
            'emp': emp_id,
            'gross': gross,
            'old_cpp': cpp,
            'new_cpp': fixed_cpp,
            'old_ded': ded,
            'new_ded': fixed_total_ded,
            'old_net': net,
            'new_net': fixed_net
        })

print(f"\n{'Status':<10} {'Count':<8} {'%'}")
print("-"*25)
print(f"{'Safe':<10} {len(records)-len(problematic):<8} {100*(len(records)-len(problematic))/max(1,len(records)):.1f}%")
print(f"{'Violate':<10} {len(problematic):<8} {100*len(problematic)/max(1,len(records)):.1f}%")

if problematic:
    print(f"\n" + "="*100)
    print("RECORDS THAT WOULD VIOLATE CHECK CONSTRAINT AFTER CPP FIX")
    print("="*100)
    print(f"\n{'ID':<8} {'Employee':<12} {'Gross':<15} {'Old CPP':<15} {'New CPP':<15} {'New Deductions':<18} {'New Net':<15}")
    print("-"*100)
    
    for rec in problematic[:20]:
        print(f"{rec['id']:<8} {rec['emp']:<12} ${rec['gross']:>12,.2f} ${rec['old_cpp']:>12,.2f} ${rec['new_cpp']:>12,.2f} ${rec['new_ded']:>15,.2f} ${rec['new_net']:>12,.2f}")
    
    if len(problematic) > 20:
        print(f"... and {len(problematic)-20} more")
    
    print(f"\n⚠️  Solution options:")
    print(f"   1. Use 'CONSTRAINT cpp_fix' with temporary disable:")
    print(f"      ALTER TABLE employee_pay_master DISABLE TRIGGER ALL;")
    print(f"      -- run fix --")
    print(f"      ALTER TABLE employee_pay_master ENABLE TRIGGER ALL;")
    print(f"")
    print(f"   2. Fix records that CAN be fixed, flag problematic ones for review:")
    print(f"      - Fix {len(records)-len(problematic)} safe records")
    print(f"      - Create audit table for {len(problematic)} records needing manual review")
    print(f"")
    print(f"   3. Temporarily disable check constraint:")
    print(f"      ALTER TABLE employee_pay_master DROP CONSTRAINT check_net;")
    print(f"      -- run fix --")
    print(f"      ALTER TABLE employee_pay_master ADD CONSTRAINT check_net CHECK ((net_pay IS NULL) OR (net_pay >= 0));")
else:
    print(f"\n✅ All {len(records)} records can be safely fixed without violating constraint!")

cur.close()
conn.close()
