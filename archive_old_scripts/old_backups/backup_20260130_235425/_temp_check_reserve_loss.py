#!/usr/bin/env python3
"""Check which payments are missing reserve_number"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("\n" + "="*80)
print("RESERVE_NUMBER DATA LOSS ANALYSIS")
print("="*80)

# 1. Total breakdown
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) as has_reserve,
        COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as no_reserve,
        COUNT(CASE WHEN charter_id IS NOT NULL AND charter_id != 0 THEN 1 END) as has_charter_id
    FROM payments
""")
total, has_res, no_res, has_charter = cur.fetchone()
print(f"\n📊 Overall reserve_number status:")
print(f"   Total payments: {total:,}")
print(f"   Has reserve_number: {has_res:,} ({has_res/total*100:.1f}%)")
print(f"   Missing reserve_number: {no_res:,} ({no_res/total*100:.1f}%)")
print(f"   Has charter_id: {has_charter:,} ({has_charter/total*100:.1f}%)")

# 2. By payment year
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM payment_date) as year,
        COUNT(*) as total,
        COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as no_reserve,
        COUNT(CASE WHEN payment_key LIKE 'ETR:%' THEN 1 END) as etr_payments
    FROM payments
    GROUP BY EXTRACT(YEAR FROM payment_date)
    ORDER BY year DESC
""")

print(f"\n📅 Reserve_number gaps by year:")
print(f"{'Year':<6} {'Total':<8} {'No Reserve':<12} {'%Missing':<10} {'ETR Payments':<15}")
print("-" * 70)
for year, tot, no_res, etr in cur.fetchall():
    year_str = str(int(year)) if year else "NULL"
    pct = (no_res/tot*100) if tot > 0 else 0
    print(f"{year_str:<6} {tot:<8,} {no_res:<12,} {pct:>8.1f}%  {etr:<15,}")

# 3. Payments with ETR key but no reserve
cur.execute("""
    SELECT 
        payment_id,
        payment_date,
        amount,
        payment_key,
        payment_method,
        charter_id
    FROM payments
    WHERE payment_key LIKE 'ETR:%'
    AND reserve_number IS NULL
    ORDER BY payment_date DESC
    LIMIT 15
""")

print(f"\n🔍 Sample ETR payments WITHOUT reserve_number:")
print(f"{'ID':<8} {'Date':<12} {'Amount':<12} {'ETR Key':<15} {'Method':<15} {'Charter ID':<12}")
print("-" * 90)
for pid, dt, amt, key, method, charter_id in cur.fetchall():
    dt_str = dt.strftime("%Y-%m-%d") if dt else "None"
    charter_str = str(charter_id) if charter_id else "NULL"
    print(f"{pid:<8} {dt_str:<12} ${amt:>10,.2f} {(key or '')[:13]:<15} {(method or 'NULL'):<15} {charter_str:<12}")

# 4. Can we recover reserve from charter_id?
cur.execute("""
    SELECT 
        COUNT(*) as recoverable
    FROM payments p
    INNER JOIN charters c ON c.charter_id = p.charter_id
    WHERE p.reserve_number IS NULL
    AND c.reserve_number IS NOT NULL
""")
recoverable = cur.fetchone()[0]

print(f"\n💡 Potential recovery:")
print(f"   {recoverable:,} payments have charter_id but missing reserve_number")
print(f"   These can be recovered from charters.reserve_number")

cur.close()
conn.close()
print("\n" + "="*80)
