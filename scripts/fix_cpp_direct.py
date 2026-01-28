#!/usr/bin/env python3
"""
Simple direct fix without the problematic ABS() issue.
Use direct CASE statement and then recalculate.
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
print("DIRECT FIX: FLIP CPP SIGN USING CASE, THEN RECALCULATE TOTALS")
print("="*90)

print("\n1️⃣  Checking current state...")
cur.execute('SELECT COUNT(*) FROM employee_pay_master WHERE cpp_employee < 0')
negative_before = cur.fetchone()[0]
cur.execute('SELECT SUM(cpp_employee) FROM employee_pay_master')
cpp_sum_before = cur.fetchone()[0]

print(f"   Negative CPP records: {negative_before}")
print(f"   Total CPP: ${cpp_sum_before:,.2f}")

# Step 1: Flip negative CPP signs only
print("\n2️⃣  Flipping negative CPP signs...")
try:
    cur.execute("""
        UPDATE employee_pay_master
        SET cpp_employee = -cpp_employee
        WHERE cpp_employee < 0
    """)
    rows_flipped = cur.rowcount
    print(f"   ✅ Flipped {rows_flipped} records")
except Exception as e:
    print(f"   ❌ Flip failed: {e}")
    conn.rollback()
    cur.close()
    conn.close()
    exit(1)

# Step 2: Recalculate total_deductions and net_pay
print("\n3️⃣  Recalculating total_deductions and net_pay...")
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

# Step 3: Commit
print("\n4️⃣  Committing changes...")
try:
    conn.commit()
    print("   ✅ Transaction committed")
except Exception as e:
    print(f"   ❌ Commit failed: {e}")
    cur.close()
    conn.close()
    exit(1)

# Verification
print("\n5️⃣  Verification...")
cur.execute('SELECT COUNT(*) FROM employee_pay_master WHERE cpp_employee < 0')
negative_after = cur.fetchone()[0]

cur.execute('SELECT SUM(cpp_employee) FROM employee_pay_master')
cpp_sum_after = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM employee_pay_master WHERE net_pay < 0')
negative_net = cur.fetchone()[0]

print(f"   Negative CPP before: {negative_before} → After: {negative_after}")
print(f"   CPP total before: ${cpp_sum_before:,.2f} → After: ${cpp_sum_after:,.2f}")
print(f"   Negative net_pay records: {negative_net}")

if negative_after == 0 and cpp_sum_after > 0:
    print("\n   ✅ SUCCESS: All CPP values corrected!")
else:
    print(f"\n   ⚠️  Issue: negative_after={negative_after}, cpp_sum_after=${cpp_sum_after:,.2f}")

print("\n" + "="*90)
print("SUMMARY")
print("="*90)
print(f"Records flipped: {rows_flipped}")
print(f"Records recalculated: {rows_recalc}")
print(f"CPP total changed from ${cpp_sum_before:,.2f} to ${cpp_sum_after:,.2f}")
print(f"Negative net_pay violations: {negative_net}")
print("="*90)

cur.close()
conn.close()
