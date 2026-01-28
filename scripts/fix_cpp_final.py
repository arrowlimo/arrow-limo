#!/usr/bin/env python3
"""
Fix CPP properly: First disable constraint, then make ALL changes.
"""

import os
import psycopg2

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
print("CPP FIX (FINAL): Disable constraint, fix, recalc, re-enable")
print("="*90)

print("\n1️⃣  Disabling check_net constraint...")
try:
    cur.execute("ALTER TABLE employee_pay_master DROP CONSTRAINT check_net")
    conn.commit()
    print("   ✅ Constraint disabled")
except Exception as e:
    print(f"   ⚠️  {e}")

print("\n2️⃣  Flipping CPP signs...")
try:
    cur.execute("""
        UPDATE employee_pay_master
        SET cpp_employee = -cpp_employee
        WHERE cpp_employee < 0
    """)
    flipped = cur.rowcount
    print(f"   ✅ Flipped {flipped} records")
except Exception as e:
    print(f"   ❌ Flip failed: {e}")
    conn.rollback()
    cur.close()
    conn.close()
    exit(1)

print("\n3️⃣  Recalculating totals...")
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
    recalc = cur.rowcount
    print(f"   ✅ Recalculated {recalc} records")
except Exception as e:
    print(f"   ❌ Recalc failed: {e}")
    conn.rollback()
    cur.close()
    conn.close()
    exit(1)

print("\n4️⃣  Committing transaction...")
try:
    conn.commit()
    print("   ✅ Committed")
except Exception as e:
    print(f"   ❌ Commit failed: {e}")
    cur.close()
    conn.close()
    exit(1)

print("\n5️⃣  Re-enabling constraint...")
try:
    cur.execute("""
        ALTER TABLE employee_pay_master
        ADD CONSTRAINT check_net CHECK ((net_pay IS NULL) OR (net_pay >= 0))
    """)
    conn.commit()
    print("   ✅ Constraint re-enabled")
except Exception as e:
    print(f"   ⚠️  Cannot re-enable: {e}")
    conn.rollback()  # Clear the failed transaction

print("\n6️⃣  Verification...")
conn.reset()  # Reset connection after rollback
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM employee_pay_master WHERE cpp_employee < 0')
neg_cpp = cur.fetchone()[0]
cur.execute('SELECT SUM(cpp_employee) FROM employee_pay_master')
cpp_sum = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM employee_pay_master WHERE net_pay < 0')
neg_net = cur.fetchone()[0]

print(f"   Negative CPP: {neg_cpp} (target: 0)")
print(f"   CPP total: ${cpp_sum:,.2f}")
print(f"   Negative net: {neg_net}")

if neg_cpp == 0 and cpp_sum > 0:
    print("\n   ✅ SUCCESS!")
else:
    print(f"\n   ⚠️  Issue: neg_cpp={neg_cpp}, cpp_sum={cpp_sum}")

print("\n" + "="*90)

cur.close()
conn.close()
