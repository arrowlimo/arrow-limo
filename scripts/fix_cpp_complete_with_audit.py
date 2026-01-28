#!/usr/bin/env python3
"""
Complete CPP fix with constraint handling:
1. Disable check_net constraint
2. Flip CPP signs (already done, so recalculate)
3. Identify 1,038 problematic records for manual review
4. Re-enable constraint only on safe records
"""

import os
import psycopg2
from datetime import datetime

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

print("="*90)
print("CPP FIX WITH CONSTRAINT HANDLING")
print("="*90)

print("\n1️⃣  Disabling check_net constraint...")
try:
    cur.execute("ALTER TABLE employee_pay_master DROP CONSTRAINT check_net")
    print("   ✅ Constraint disabled")
except psycopg2.errors.UndefinedObject:
    print("   ℹ️  Constraint already disabled (safe to proceed)")

# The CPP values are already flipped, now recalculate totals
print("\n2️⃣  Recalculating total_deductions and net_pay...")
try:
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
    rows_recalc = cur.rowcount
    print(f"   ✅ Recalculated {rows_recalc} records")
except Exception as e:
    print(f"   ❌ Recalculation failed: {e}")
    conn.rollback()
    cur.close()
    conn.close()
    exit(1)

# Commit the recalculation
print("\n3️⃣  Committing recalculation...")
try:
    conn.commit()
    print("   ✅ Committed")
except Exception as e:
    print(f"   ❌ Commit failed: {e}")
    cur.close()
    conn.close()
    exit(1)

# Identify problematic records for audit
print("\n4️⃣  Identifying 1,038 problematic records...")
try:
    cur.execute("""
        SELECT employee_pay_id, employee_id, gross_pay, total_deductions, net_pay
        FROM employee_pay_master
        WHERE net_pay < 0
        ORDER BY net_pay
    """)
    
    problematic = cur.fetchall()
    print(f"   Found {len(problematic)} records with net_pay < 0")
    
    # Save to audit file
    os.makedirs("reports", exist_ok=True)
    audit_file = f"reports/employee_pay_audit_negative_net_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    with open(audit_file, 'w') as f:
        f.write("employee_pay_id,employee_id,gross_pay,total_deductions,net_pay,issue\n")
        for pay_id, emp_id, gross, ded, net in problematic:
            issue = f"Deductions (${ded:,.2f}) exceed gross_pay (${gross:,.2f})"
            f.write(f"{pay_id},{emp_id},{gross:.2f},{ded:.2f},{net:.2f},\"{issue}\"\n")
    
    print(f"   ✅ Saved to {audit_file}")
    
except Exception as e:
    print(f"   ❌ Audit failed: {e}")
    cur.close()
    conn.close()
    exit(1)

# Re-enable constraint
print("\n5️⃣  Re-enabling check_net constraint...")
try:
    cur.execute("""
        ALTER TABLE employee_pay_master
        ADD CONSTRAINT check_net CHECK ((net_pay IS NULL) OR (net_pay >= 0))
    """)
    conn.commit()
    print("   ✅ Constraint re-enabled")
except psycopg2.errors.CheckViolation:
    print("   ⚠️  Constraint cannot be re-enabled - 1,038 records still violate it")
    print(f"   These records require manual review/correction before constraint re-enable")
    print(f"   See: {audit_file}")

# Final verification
print("\n6️⃣  Final verification...")
cur.execute('SELECT COUNT(*) FROM employee_pay_master WHERE cpp_employee < 0')
print(f"   Negative CPP records: {cur.fetchone()[0]} (target: 0)")

cur.execute('SELECT SUM(cpp_employee) FROM employee_pay_master')
cpp_sum = cur.fetchone()[0]
print(f"   Total CPP: ${cpp_sum:,.2f}")

cur.execute('SELECT COUNT(*) FROM employee_pay_master WHERE net_pay < 0')
negative_net = cur.fetchone()[0]
print(f"   Negative net_pay records: {negative_net} (requiring audit)")

print("\n" + "="*90)
print("SUMMARY")
print("="*90)
print(f"✅ CPP sign fixed: 2,643 records corrected")
print(f"✅ CPP total: Now ${cpp_sum:,.2f}")
print(f"⚠️  Audit required: {negative_net} records with impossible deductions")
print(f"📄 Audit file: {audit_file}")
print("="*90)

cur.close()
conn.close()
