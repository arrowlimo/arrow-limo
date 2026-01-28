#!/usr/bin/env python3
"""Check payment_key ETR: vs payment_method e_transfer"""
import psycopg2

conn = psycopg2.connect(host="localhost", database="almsdata", user="postgres", password="***REMOVED***")
cur = conn.cursor()

print("\n" + "="*70)
print("PAYMENT_KEY vs PAYMENT_METHOD COMPARISON")
print("="*70)

# 1. payment_method breakdown with ETR key counts
cur.execute("""
    SELECT 
        COALESCE(payment_method, 'NULL') as method,
        COUNT(*) as total,
        COUNT(CASE WHEN payment_key LIKE 'ETR:%' THEN 1 END) as has_etr_key,
        COUNT(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 END) as matched
    FROM payments
    WHERE reserve_number IS NOT NULL
    GROUP BY payment_method
    ORDER BY total DESC
""")

print("\n📊 Payment method vs ETR key markers:")
print(f"{'Method':<20} {'Total':<10} {'ETR: Key':<12} {'Matched':<10}")
print("-" * 60)
for method, total, etr_key, matched in cur.fetchall():
    print(f"{method:<20} {total:<10,} {etr_key:<12,} {matched:<10,}")

# 2. Payments with ETR: key but NOT method='e_transfer'
cur.execute("""
    SELECT 
        payment_method,
        COUNT(*) as cnt
    FROM payments
    WHERE payment_key LIKE 'ETR:%'
    AND payment_method != 'e_transfer'
    GROUP BY payment_method
""")

print(f"\n🔍 Payments with 'ETR:' key but DIFFERENT payment_method:")
rows = cur.fetchall()
if rows:
    for method, cnt in rows:
        print(f"   {method or 'NULL'}: {cnt:,}")
else:
    print("   (None - all ETR: keys have method='e_transfer')")

# 3. Sample ETR: keys
cur.execute("""
    SELECT payment_id, reserve_number, payment_key, payment_method, amount, payment_date, banking_transaction_id
    FROM payments
    WHERE payment_key LIKE 'ETR:%'
    AND banking_transaction_id IS NULL
    LIMIT 10
""")

print(f"\n📋 Sample UNMATCHED payments with ETR: keys:")
print(f"{'ID':<8} {'Reserve':<10} {'Key':<30} {'Method':<15} {'Amount':<12} {'Date':<12}")
print("-" * 100)
for row in cur.fetchall():
    pid, res, key, method, amt, dt, bank_id = row
    dt_str = dt.strftime("%Y-%m-%d") if dt else "None"
    amt_val = float(amt) if amt is not None else 0.0
    res_str = str(res) if res is not None else "NULL"
    key_str = (key or '')[:28]
    print(f"{pid:<8} {res_str:<10} {key_str:<30} {method or 'NULL':<15} ${amt_val:>10,.2f} {dt_str}")

cur.close()
conn.close()
print("\n" + "="*70)
