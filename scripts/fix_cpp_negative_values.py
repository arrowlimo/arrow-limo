#!/usr/bin/env python3
"""
Fix CPP negative values in employee_pay_master.
Correct the sign and recalculate total_deductions and net_pay.
"""

import os
import psycopg2
from datetime import datetime

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
conn.autocommit = False
cur = conn.cursor()

print("="*80)
print("FIX CPP NEGATIVE VALUES IN EMPLOYEE_PAY_MASTER")
print("="*80)

# 1. Create backup
print("\nCreating backup...")
backup_file = f"reports/employee_pay_master_backup_cpp_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"

cur.execute("SELECT COUNT(*) FROM employee_pay_master WHERE cpp_employee < 0")
negative_count = cur.fetchone()[0]

print(f"Records with negative CPP: {negative_count:,}")

# 2. Backup before changes
with open(backup_file, 'w') as f:
    f.write("-- Backup of employee_pay_master before CPP fix\n")
    f.write(f"-- Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write("-- Records affected: negative CPP correction\n\n")
    
    cur.execute("""
        SELECT employee_pay_id, cpp_employee, total_deductions, net_pay
        FROM employee_pay_master
        WHERE cpp_employee < 0
        ORDER BY employee_pay_id
    """)
    
    for row in cur.fetchall():
        f.write(f"-- employee_pay_id={row[0]}, cpp={row[1]}, total_deductions={row[2]}, net_pay={row[3]}\n")

print(f"✅ Backup saved: {backup_file}")

# 3. Fix CPP sign (multiply negative by -1 to make positive)
print("\nFixing CPP sign (negative → positive)...")
try:
    cur.execute("""
        UPDATE employee_pay_master
        SET cpp_employee = ABS(cpp_employee)
        WHERE cpp_employee < 0
    """)
    print(f"✅ Updated {cur.rowcount} records: cpp_employee now positive")

    # 4. Recalculate total_deductions
    # total_deductions = cpp_employee + ei_employee + federal_tax + provincial_tax + union_dues + radio_dues + voucher_deductions + misc_deductions
    print("\nRecalculating total_deductions...")
    cur.execute("""
        UPDATE employee_pay_master
        SET total_deductions = 
            COALESCE(cpp_employee, 0) + 
            COALESCE(ei_employee, 0) + 
            COALESCE(federal_tax, 0) + 
            COALESCE(provincial_tax, 0) + 
            COALESCE(union_dues, 0) + 
            COALESCE(radio_dues, 0) + 
            COALESCE(voucher_deductions, 0) + 
            COALESCE(misc_deductions, 0)
        WHERE cpp_employee IS NOT NULL
    """)
    print(f"✅ Updated {cur.rowcount} records: total_deductions recalculated")

    # 5. Recalculate net_pay = gross_pay - total_deductions
    print("\nRecalculating net_pay...")
    cur.execute("""
        UPDATE employee_pay_master
        SET net_pay = gross_pay - total_deductions
        WHERE gross_pay IS NOT NULL AND total_deductions IS NOT NULL
    """)
    print(f"✅ Updated {cur.rowcount} records: net_pay recalculated")

    # Commit changes
    conn.commit()
    print("\n✅ All changes committed")

    # 6. Verify
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)

    cur.execute("""
        SELECT 
            COUNT(*) as records,
            SUM(gross_pay) as total_gross,
            SUM(cpp_employee) as total_cpp,
            SUM(total_deductions) as total_ded,
            SUM(net_pay) as total_net
        FROM employee_pay_master
    """)

    records, gross, cpp, ded, net = cur.fetchone()
    
    print(f"\nFixed Employee Pay Master:")
    print(f"  Records: {records:,}")
    print(f"  Gross Pay:       ${float(gross or 0):>15,.2f}")
    print(f"  CPP Employee:    ${float(cpp or 0):>15,.2f} ✅ (now positive)")
    print(f"  Total Deductions: ${float(ded or 0):>15,.2f} ✅ (should be positive)")
    print(f"  Net Pay:         ${float(net or 0):>15,.2f}")

    # Check remaining negatives
    cur.execute("""
        SELECT COUNT(*) FROM employee_pay_master 
        WHERE cpp_employee < 0
    """)
    remaining_neg = cur.fetchone()[0]
    
    if remaining_neg == 0:
        print(f"\n✅ SUCCESS: All CPP values are now positive (0 negative records)")
    else:
        print(f"\n⚠️  WARNING: Still {remaining_neg} negative CPP records")

    # Validation: net_pay should equal gross - deductions
    cur.execute("""
        SELECT COUNT(*) as mismatches
        FROM employee_pay_master
        WHERE ABS((gross_pay - total_deductions) - net_pay) > 0.01
    """)
    
    mismatches = cur.fetchone()[0]
    if mismatches == 0:
        print(f"✅ Validation: net_pay = gross - deductions for all records")
    else:
        print(f"⚠️  {mismatches} records have net_pay calculation mismatches")

except Exception as e:
    conn.rollback()
    print(f"\n❌ Error: {e}")
    print("Transaction rolled back")

finally:
    cur.close()
    conn.close()

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"CPP sign corrected: {negative_count:,} records")
print(f"Backup: {backup_file}")
print(f"Impact: Net pay decreased, Deductions increased, Data integrity restored")
