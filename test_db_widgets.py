#!/usr/bin/env python
"""Quick test to verify database and widget queries work"""

import os
import psycopg2
from datetime import datetime

# Database connection
conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
    database=os.getenv("DB_NAME", "almsdata"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "***REMOVED***")
)

cur = conn.cursor()

print("=" * 60)
print("DATABASE CONNECTIVITY & WIDGET DATA TEST")
print("=" * 60)

# Test 1: Table exists
print("\n1️⃣  VEHICLES TABLE:")
try:
    cur.execute("SELECT COUNT(*) FROM vehicles")
    count = cur.fetchone()[0]
    print(f"   ✅ vehicles table found ({count} rows)")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 2: Fleet Management query
print("\n2️⃣  FLEET MANAGEMENT QUERY:")
try:
    cur.execute("""SELECT v.vehicle_number, v.make, v.model, v.year,
        COALESCE(SUM(CASE WHEN r.description ILIKE '%fuel%' THEN r.gross_amount ELSE 0 END),0) fuel_cost,
        COALESCE(SUM(CASE WHEN r.description ILIKE '%maint%' OR r.description ILIKE '%repair%' THEN r.gross_amount ELSE 0 END),0) maint_cost
        FROM vehicles v
        LEFT JOIN receipts r ON v.vehicle_id = r.vehicle_id
        GROUP BY v.vehicle_id, v.vehicle_number, v.make, v.model, v.year
        ORDER BY v.vehicle_number""")
    rows = cur.fetchall()
    print(f"   ✅ Query returned {len(rows)} vehicles")
    for i, row in enumerate(rows[:3]):
        print(f"      [{i+1}] {row[0]:15} {row[1]} {row[2]} {row[3]} | Fuel: ${float(row[4]):.2f} Maint: ${float(row[5]):.2f}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 3: Driver Performance query
print("\n3️⃣  DRIVER PERFORMANCE QUERY:")
try:
    cur.execute("""SELECT e.full_name, COUNT(*) charters,
        SUM(dp.gross_pay) gross, SUM(dp.total_deductions) deductions, SUM(dp.net_pay) net
        FROM employees e
        LEFT JOIN driver_payroll dp ON e.employee_id = dp.employee_id
        WHERE e.is_chauffeur = true
        GROUP BY e.employee_id, e.full_name
        ORDER BY gross DESC""")
    rows = cur.fetchall()
    print(f"   ✅ Query returned {len(rows)} drivers")
    for i, row in enumerate(rows[:3]):
        gross = float(row[2]) if row[2] else 0
        print(f"      [{i+1}] {row[0]:20} Charters: {int(row[1]) if row[1] else 0:3} | Gross: ${gross:,.2f}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 4: Financial Dashboard query
print("\n4️⃣  FINANCIAL DASHBOARD QUERY (Sample):")
try:
    cur.execute("""SELECT 
        (SELECT COUNT(*) FROM charters) total_charters,
        (SELECT COUNT(*) FROM payments) total_payments,
        (SELECT COALESCE(SUM(amount),0) FROM payments) revenue,
        (SELECT COALESCE(SUM(gross_amount),0) FROM receipts) expenses""")
    total_charters, total_payments, revenue, expenses = cur.fetchone()
    print(f"   ✅ Financial data retrieved:")
    print(f"      Total Charters: {total_charters}")
    print(f"      Total Payments: {total_payments}")
    print(f"      Revenue: ${float(revenue):,.2f}")
    print(f"      Expenses: ${float(expenses):,.2f}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 5: Receipts table schema
print("\n5️⃣  RECEIPTS TABLE SCHEMA:")
try:
    cur.execute("""SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name='receipts'
        ORDER BY ordinal_position""")
    cols = cur.fetchall()
    print(f"   ✅ Receipts table has {len(cols)} columns:")
    for col in cols[:10]:
        print(f"      - {col[0]:30} ({col[1]})")
    if len(cols) > 10:
        print(f"      ... and {len(cols)-10} more")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 6: Payment reconciliation sample
print("\n6️⃣  PAYMENT RECONCILIATION SAMPLE:")
try:
    cur.execute("""SELECT 
        c.reserve_number,
        c.charter_date,
        c.total_amount_due,
        SUM(p.amount) paid,
        c.total_amount_due - COALESCE(SUM(p.amount), 0) balance
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due
        LIMIT 5""")
    rows = cur.fetchall()
    print(f"   ✅ Sample charter-payment reconciliation:")
    for row in rows:
        print(f"      {row[0]:10} | {row[1]} | Due: ${float(row[2]):,.2f} | Paid: ${float(row[3]) if row[3] else 0:,.2f} | Bal: ${float(row[4]):,.2f}")
except Exception as e:
    print(f"   ❌ Error: {e}")

cur.close()
conn.close()

print("\n" + "=" * 60)
print("✅ TEST COMPLETE")
print("=" * 60)
