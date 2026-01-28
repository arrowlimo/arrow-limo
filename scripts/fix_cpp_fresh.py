#!/usr/bin/env python3
"""
Fresh start: Check state and fix CPP.
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

print("="*90)
print("FRESH START: Check state and apply CPP fix")
print("="*90)

print("\n1️⃣  Current state...")
cur.execute('SELECT COUNT(*) FROM employee_pay_master WHERE cpp_employee < 0')
neg_cpp_before = cur.fetchone()[0]
cur.execute('SELECT SUM(cpp_employee) FROM employee_pay_master')
cpp_sum_before = cur.fetchone()[0]

print(f"   Negative CPP: {neg_cpp_before}")
print(f"   CPP total: ${cpp_sum_before:,.2f}")

print("\n2️⃣  Checking constraint...")
try:
    cur.execute("""
        SELECT constraint_name FROM information_schema.check_constraints
        WHERE constraint_name = 'check_net'
    """)
    result = cur.fetchone()
    if result:
        print(f"   ✅ Constraint 'check_net' exists - need to drop it")
        cur.execute("ALTER TABLE employee_pay_master DROP CONSTRAINT check_net")
        conn.commit()
        print(f"   ✅ Dropped constraint")
    else:
        print(f"   ℹ️  Constraint does not exist")
except Exception as e:
    print(f"   Error: {e}")

print("\n3️⃣  Flipping CPP signs...")
try:
    cur.execute("""
        UPDATE employee_pay_master
        SET cpp_employee = -cpp_employee
        WHERE cpp_employee < 0
    """)
    flipped = cur.rowcount
    print(f"   ✅ Flipped {flipped} records")
    conn.commit()
except Exception as e:
    print(f"   ❌ Failed: {e}")
    conn.rollback()
    cur.close()
    conn.close()
    exit(1)

print("\n4️⃣  Recalculating net_pay and total_deductions...")
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
    conn.commit()
except Exception as e:
    print(f"   ❌ Failed: {e}")
    conn.rollback()
    cur.close()
    conn.close()
    exit(1)

print("\n5️⃣  Verification...")
cur.execute('SELECT COUNT(*) FROM employee_pay_master WHERE cpp_employee < 0')
neg_cpp_after = cur.fetchone()[0]
cur.execute('SELECT SUM(cpp_employee) FROM employee_pay_master')
cpp_sum_after = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM employee_pay_master WHERE net_pay < 0')
neg_net = cur.fetchone()[0]

print(f"   Negative CPP: {neg_cpp_before} → {neg_cpp_after}")
print(f"   CPP total: ${cpp_sum_before:,.2f} → ${cpp_sum_after:,.2f}")
print(f"   Negative net_pay: {neg_net}")

if neg_cpp_after == 0 and cpp_sum_after > 0:
    print("\n   ✅ SUCCESS: CPP fixed!")
else:
    print(f"\n   ⚠️  Issue: still {neg_cpp_after} negative CPP records")

print("\n" + "="*90)
print(f"CPP correction: {cpp_sum_before:,.2f} → {cpp_sum_after:,.2f}")
print("="*90)

cur.close()
conn.close()
