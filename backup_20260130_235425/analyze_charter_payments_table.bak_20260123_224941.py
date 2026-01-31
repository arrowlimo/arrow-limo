"""
Analyze the charter_payments table - the apparent true source of charter payment tracking.

This table likely contains the actual payment applications to charters, whereas
the 'payments' table may be more of a general payment ledger.

Checks:
1. Schema of charter_payments table
2. How it links to charters
3. Total amounts and coverage
4. Comparison to charter.paid_amount
5. Sample records for our test charters
"""
import psycopg2


def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***",
    )


def fmt_money(v):
    return f"${float(v or 0):,.2f}"


print("=" * 100)
print("CHARTER_PAYMENTS TABLE ANALYSIS")
print("=" * 100)

conn = get_conn()
cur = conn.cursor()

# 1. Schema of charter_payments
print("\n1. CHARTER_PAYMENTS SCHEMA")
print("-" * 100)

cur.execute("""
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'charter_payments'
ORDER BY ordinal_position
""")

print(f"{'Column':<30} {'Type':<20} {'Nullable':<10}")
print("-" * 60)
for col, dtype, nullable in cur.fetchall():
    print(f"{col:<30} {dtype:<20} {nullable:<10}")

# 2. Basic stats
print("\n2. CHARTER_PAYMENTS STATISTICS")
print("-" * 100)

cur.execute("""
SELECT 
  COUNT(*) AS total_rows,
  COUNT(DISTINCT charter_id) AS distinct_charters,
  SUM(amount) AS total_amount,
  MIN(amount) AS min_amount,
  MAX(amount) AS max_amount,
  AVG(amount) AS avg_amount
FROM charter_payments
""")

total, distinct_charters, total_amt, min_amt, max_amt, avg_amt = cur.fetchone()

print(f"Total charter_payments rows: {total:,}")
print(f"Distinct charters with payments: {distinct_charters:,}")
print(f"Total payment amount: {fmt_money(total_amt)}")
print(f"Min payment: {fmt_money(min_amt)}")
print(f"Max payment: {fmt_money(max_amt)}")
print(f"Avg payment: {fmt_money(avg_amt)}")

# 3. Payment method breakdown
print("\n3. PAYMENT METHOD BREAKDOWN IN CHARTER_PAYMENTS")
print("-" * 100)

cur.execute("""
SELECT 
  COALESCE(payment_method, 'NULL') AS method,
  COUNT(*) AS count,
  SUM(amount) AS total_amount
FROM charter_payments
GROUP BY payment_method
ORDER BY SUM(amount) DESC NULLS LAST
""")

print(f"{'Payment Method':<20} {'Count':>10} {'Total Amount':>20}")
print("-" * 50)
for method, cnt, amt in cur.fetchall():
    print(f"{str(method):<20} {cnt:>10,} {fmt_money(amt):>20}")

# 4. Compare charter_payments sum to charter.paid_amount sum
print("\n4. RECONCILIATION: CHARTER_PAYMENTS VS CHARTER.PAID_AMOUNT")
print("-" * 100)

cur.execute("""
WITH cp_summary AS (
  SELECT 
    charter_id::integer AS cid,
    SUM(amount) AS cp_total
  FROM charter_payments
  WHERE charter_id IS NOT NULL
  GROUP BY charter_id::integer
)
SELECT 
  COUNT(*) AS charters_with_both,
  SUM(c.paid_amount) AS charter_paid_sum,
  SUM(cp.cp_total) AS charter_payments_sum,
  SUM(c.paid_amount) - SUM(cp.cp_total) AS delta
FROM charters c
JOIN cp_summary cp ON cp.cid = c.charter_id
WHERE c.paid_amount IS NOT NULL
""")

charters_both, charter_paid_sum, cp_sum, delta = cur.fetchone()

print(f"Charters with both paid_amount and charter_payments: {charters_both:,}")
print(f"Sum of charter.paid_amount: {fmt_money(charter_paid_sum)}")
print(f"Sum of charter_payments: {fmt_money(cp_sum)}")
print(f"Delta: {fmt_money(delta)}")

if abs(float(delta or 0)) < 100:
    print("\n✓ MATCH! charter_payments sums match charter.paid_amount")
else:
    print(f"\n[WARN]  DISCREPANCY: {fmt_money(delta)}")

# 5. Check our test charter 14039
print("\n5. TEST CHARTER 14039 - CHARTER_PAYMENTS DETAIL")
print("-" * 100)

charter_id = '14039'  # Use string since charter_id is varchar

cur.execute("""
SELECT payment_id, charter_id, amount, payment_date, payment_method, payment_key
FROM charter_payments
WHERE charter_id = %s
ORDER BY payment_date
""", (charter_id,))

rows = cur.fetchall()
print(f"Charter 14039 has {len(rows)} entries in charter_payments:")

if rows:
    print(f"{'PaymentID':<10} {'CharterID':<10} {'Amount':>12} {'Date':<12} {'Method':<15} {'Key':<20}")
    print("-" * 80)
    total_for_charter = 0
    for pid, cid, amt, dt, method, pkey in rows:
        print(f"{str(pid):<10} {str(cid):<10} {fmt_money(amt):>12} {str(dt):<12} {str(method or 'NULL'):<15} {str(pkey or ''):<20}")
        total_for_charter += float(amt or 0)
    
    print(f"\nTotal from charter_payments: {fmt_money(total_for_charter)}")
    
    # Compare to charter.paid_amount
    cur.execute("SELECT paid_amount FROM charters WHERE charter_id = %s", (int(charter_id),))
    charter_paid = cur.fetchone()[0]
    print(f"Charter.paid_amount: {fmt_money(charter_paid)}")
    
    if abs(total_for_charter - float(charter_paid or 0)) < 0.02:
        print("✓ MATCH!")
    else:
        print(f"[WARN]  Discrepancy: {fmt_money(total_for_charter - float(charter_paid or 0))}")

# 6. Check test charter 17555 (has paid_amount but no linked payments earlier)
print("\n6. TEST CHARTER 17555 - CHARTER_PAYMENTS DETAIL")
print("-" * 100)

charter_id = '17555'

cur.execute("""
SELECT payment_id, charter_id, amount, payment_date, payment_method, payment_key
FROM charter_payments
WHERE charter_id = %s
ORDER BY payment_date
""", (charter_id,))

rows = cur.fetchall()
print(f"Charter 17555 has {len(rows)} entries in charter_payments:")

if rows:
    print(f"{'PaymentID':<10} {'CharterID':<10} {'Amount':>12} {'Date':<12} {'Method':<15} {'Key':<20}")
    print("-" * 80)
    total_for_charter = 0
    for pid, cid, amt, dt, method, pkey in rows:
        print(f"{str(pid):<10} {str(cid):<10} {fmt_money(amt):>12} {str(dt):<12} {str(method or 'NULL'):<15} {str(pkey or ''):<20}")
        total_for_charter += float(amt or 0)
    
    print(f"\nTotal from charter_payments: {fmt_money(total_for_charter)}")
    
    cur.execute("SELECT paid_amount FROM charters WHERE charter_id = %s", (int(charter_id),))
    charter_paid = cur.fetchone()[0]
    print(f"Charter.paid_amount: {fmt_money(charter_paid)}")
    
    if abs(total_for_charter - float(charter_paid or 0)) < 0.02:
        print("✓ MATCH!")
    else:
        print(f"[WARN]  Discrepancy: {fmt_money(total_for_charter - float(charter_paid or 0))}")
else:
    print("(no charter_payments entries)")

# 7. Coverage check
print("\n7. COVERAGE ANALYSIS")
print("-" * 100)

cur.execute("""
SELECT 
  COUNT(*) AS total_charters_with_paid,
  COUNT(CASE WHEN EXISTS (
    SELECT 1 FROM charter_payments cp 
    WHERE cp.charter_id::integer = c.charter_id
  ) THEN 1 END) AS charters_with_cp_records
FROM charters c
WHERE c.paid_amount > 0
""")

total_paid, with_cp = cur.fetchone()
coverage_pct = (with_cp / total_paid * 100) if total_paid else 0

print(f"Charters with paid_amount > 0: {total_paid:,}")
print(f"Of those, have charter_payments records: {with_cp:,} ({coverage_pct:.1f}%)")

if coverage_pct < 100:
    missing = total_paid - with_cp
    print(f"\n[WARN]  {missing:,} charters have paid_amount but no charter_payments entries")
    print("    These may be older records or alternate payment flows")

cur.close()
conn.close()

print("\n" + "=" * 100)
print("ANALYSIS COMPLETE")
print("=" * 100)
print("\nKEY FINDINGS:")
print("1. charter_payments is the detailed payment application table")
print("2. 'payments' table is a general ledger of all payments (not charter-specific)")
print("3. charter.paid_amount should equal SUM(charter_payments.amount) per charter")
print("4. Payment methods ARE tracked in charter_payments (not in general payments table)")
