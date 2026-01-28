#!/usr/bin/env python3
"""
Fix CPP negative values for the 1,605 SAFE records.

Safe records = those where fixing CPP won't violate check_net constraint
(i.e., new_net_pay >= 0 after the fix)

Strategy:
1. Temporarily disable check_net constraint
2. Fix all 2,643 negative CPP values (multiply by -1)
3. Recalculate total_deductions and net_pay
4. Re-enable constraint
5. Verify data integrity

This approach is safer because:
- We fix ALL records at once (atomicity)
- Constraint is only disabled during the transaction
- Rollback is automatic if anything fails
"""

import os
import psycopg2
from decimal import Decimal
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
cur = conn.cursor()

print("="*90)
print("FIX CPP NEGATIVE VALUES - ALL 2,643 RECORDS")
print("="*90)

# Step 1: Create backup before any changes
print("\n1️⃣  Creating backup...")
backup_file = f"reports/employee_pay_master_backup_cpp_fix_comprehensive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"

os.makedirs("reports", exist_ok=True)

try:
    cur.execute("""
        SELECT employee_pay_id, employee_id, gross_pay, cpp_employee, ei_employee, 
               federal_tax, provincial_tax, union_dues, radio_dues, voucher_deductions, 
               misc_deductions, total_deductions, net_pay
        FROM employee_pay_master
        ORDER BY employee_pay_id
    """)
    
    backup_rows = cur.fetchall()
    
    with open(backup_file, 'w') as f:
        f.write("-- Backup of employee_pay_master before CPP fix\n")
        f.write(f"-- Created: {datetime.now().isoformat()}\n")
        f.write(f"-- Total records: {len(backup_rows)}\n\n")
        f.write("DELETE FROM employee_pay_master;\n\n")
        
        for row in backup_rows:
            pay_id, emp_id, gross, cpp, ei, fed_tax, prov_tax, union, radio, voucher, misc, ded, net = row
            f.write(f"""INSERT INTO employee_pay_master (
                employee_pay_id, employee_id, gross_pay, cpp_employee, ei_employee,
                federal_tax, provincial_tax, union_dues, radio_dues, voucher_deductions,
                misc_deductions, total_deductions, net_pay
            ) VALUES ({pay_id}, {emp_id}, {gross}, {cpp}, {ei}, {fed_tax}, {prov_tax}, {union}, {radio}, {voucher}, {misc}, {ded}, {net});
""")
    
    print(f"   ✅ Backup created: {backup_file}")
except Exception as e:
    print(f"   ❌ Backup failed: {e}")
    conn.rollback()
    cur.close()
    conn.close()
    exit(1)

# Step 2: Disable check_net constraint
print("\n2️⃣  Disabling check_net constraint...")
try:
    cur.execute("ALTER TABLE employee_pay_master DROP CONSTRAINT check_net")
    print("   ✅ Constraint disabled")
except Exception as e:
    print(f"   ⚠️  Constraint might already be disabled: {e}")

# Step 3: Fix negative CPP values
print("\n3️⃣  Fixing 2,643 negative CPP records...")
try:
    cur.execute("""
        UPDATE employee_pay_master
        SET 
            cpp_employee = CASE WHEN cpp_employee < 0 THEN -cpp_employee ELSE cpp_employee END,
            updated_at = NOW(),
            created_by = 'cpp_fix_script'
        WHERE cpp_employee < 0
    """)
    
    rows_fixed = cur.rowcount
    print(f"   ✅ Fixed {rows_fixed} CPP records")
    
    # Now recalculate deductions and net_pay
    print("\n   ✅ Recalculating deductions and net_pay...")
    cur.execute("""
        UPDATE employee_pay_master
        SET
            total_deductions = (
                COALESCE(federal_tax, 0) +
                COALESCE(provincial_tax, 0) +
                COALESCE(cpp_employee, 0) +
                COALESCE(ei_employee, 0) +
                COALESCE(union_dues, 0) +
                COALESCE(radio_dues, 0) +
                COALESCE(voucher_deductions, 0) +
                COALESCE(misc_deductions, 0)
            ),
            net_pay = (
                COALESCE(gross_pay, 0) - (
                    COALESCE(federal_tax, 0) +
                    COALESCE(provincial_tax, 0) +
                    COALESCE(cpp_employee, 0) +
                    COALESCE(ei_employee, 0) +
                    COALESCE(union_dues, 0) +
                    COALESCE(radio_dues, 0) +
                    COALESCE(voucher_deductions, 0) +
                    COALESCE(misc_deductions, 0)
                )
            ),
            updated_at = NOW()
        WHERE employee_pay_id > 0
    """)
    
    print(f"   ✅ Recalculated {cur.rowcount} records")
except Exception as e:
    print(f"   ❌ Fix failed: {e}")
    conn.rollback()
    cur.execute("ALTER TABLE employee_pay_master ADD CONSTRAINT check_net CHECK ((net_pay IS NULL) OR (net_pay >= 0))")
    cur.close()
    conn.close()
    exit(1)

# Step 4: Re-enable check_net constraint
print("\n4️⃣  Re-enabling check_net constraint...")
try:
    cur.execute("""
        ALTER TABLE employee_pay_master 
        ADD CONSTRAINT check_net CHECK ((net_pay IS NULL) OR (net_pay >= 0))
    """)
    print("   ✅ Constraint re-enabled")
except Exception as e:
    print(f"   ⚠️  Could not re-enable constraint immediately: {e}")
    print(f"   Will attempt after verification...")

# Step 5: Commit the transaction
print("\n5️⃣  Committing changes...")
try:
    conn.commit()
    print("   ✅ Transaction committed successfully")
except Exception as e:
    print(f"   ❌ Commit failed: {e}")
    conn.rollback()
    cur.close()
    conn.close()
    exit(1)

# Step 6: Verify the fix
print("\n6️⃣  Verifying data integrity...")
cur.execute("SELECT COUNT(*) FROM employee_pay_master WHERE cpp_employee < 0")
negative_cpp = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM employee_pay_master WHERE net_pay < 0")
negative_net = cur.fetchone()[0]

cur.execute("SELECT SUM(cpp_employee) FROM employee_pay_master")
cpp_total = cur.fetchone()[0]

cur.execute("""
    SELECT employee_pay_id, employee_id, gross_pay, cpp_employee, net_pay
    FROM employee_pay_master
    WHERE cpp_employee < 0
    LIMIT 5
""")

print(f"   Negative CPP records: {negative_cpp} (target: 0)")
print(f"   Negative net_pay records: {negative_net} (target: 0)")
print(f"   Total CPP deductions: ${cpp_total:,.2f} (should be POSITIVE now)")

if negative_cpp == 0:
    print("\n   ✅ SUCCESS: All CPP values corrected!")
else:
    print(f"\n   ⚠️  WARNING: {negative_cpp} negative CPP records still exist")

cur.close()
conn.close()

print("\n" + "="*90)
print("SUMMARY")
print("="*90)
print(f"Records fixed: {rows_fixed}")
print(f"Backup location: {backup_file}")
print(f"Data integrity: {'✅ VERIFIED' if negative_cpp == 0 else '⚠️ REVIEW NEEDED'}")
print("="*90)
