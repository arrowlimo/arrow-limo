"""
Investigate where charter.paid_amount values are coming from if not from payments table.

Checks:
1. Do payment rows have $0.00 amounts (imported as metadata only)?
2. Are there other payment-tracking tables (charter_charges, charter_payments, etc.)?
3. Is paid_amount calculated/imported from LMS or other sources?
4. What are the payment_key patterns (LMSDEP, bank_transfer codes)?

This will help identify the true source of truth for charter payments.
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
print("PAYMENT SOURCE INVESTIGATION")
print("=" * 100)

conn = get_conn()
cur = conn.cursor()

# 1. Check payment amount distribution
print("\n1. PAYMENT AMOUNT DISTRIBUTION")
print("-" * 100)

cur.execute("""
SELECT 
  COUNT(*) AS total_rows,
  COUNT(CASE WHEN amount = 0 THEN 1 END) AS zero_amount,
  COUNT(CASE WHEN amount > 0 THEN 1 END) AS positive_amount,
  COUNT(CASE WHEN amount < 0 THEN 1 END) AS negative_amount,
  COUNT(CASE WHEN amount IS NULL THEN 1 END) AS null_amount,
  SUM(CASE WHEN amount > 0 THEN amount END) AS total_positive,
  SUM(CASE WHEN amount < 0 THEN amount END) AS total_negative
FROM payments
""")

total, zero, pos, neg, null, total_pos, total_neg = cur.fetchone()

print(f"Total payment rows: {total:,}")
print(f"  Zero amount ($0.00): {zero:,} ({zero/total*100:.1f}%)")
print(f"  Positive amount: {pos:,} ({pos/total*100:.1f}%)")
print(f"  Negative amount: {neg:,} ({neg/total*100:.1f}%)")
print(f"  NULL amount: {null:,} ({null/total*100:.1f}%)")
print(f"\nTotal positive: {fmt_money(total_pos)}")
print(f"Total negative: {fmt_money(total_neg)}")

# 2. Check if there are other payment-related tables
print("\n2. OTHER PAYMENT-RELATED TABLES")
print("-" * 100)

cur.execute("""
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND (table_name LIKE '%payment%' 
       OR table_name LIKE '%charge%'
       OR table_name LIKE '%receipt%'
       OR table_name LIKE '%transaction%')
ORDER BY table_name
""")

tables = cur.fetchall()
print(f"Found {len(tables)} payment-related tables:")
for (tbl,) in tables:
    cur.execute(f"SELECT COUNT(*) FROM {tbl}")
    cnt = cur.fetchone()[0]
    print(f"  {tbl:<40} {cnt:>10,} rows")

# 3. Check charter_charges table if it exists
print("\n3. CHARTER_CHARGES TABLE INVESTIGATION")
print("-" * 100)

cur.execute("""
SELECT EXISTS (
  SELECT 1 FROM information_schema.tables 
  WHERE table_name = 'charter_charges'
)
""")
has_charges = cur.fetchone()[0]

if has_charges:
    cur.execute("""
    SELECT 
      COUNT(*) AS total_charges,
      SUM(amount) AS total_amount,
      COUNT(DISTINCT charter_id) AS distinct_charters
    FROM charter_charges
    """)
    
    total_charges, total_amt, distinct_charters = cur.fetchone()
    print(f"Total charter_charges rows: {total_charges:,}")
    print(f"Total charges amount: {fmt_money(total_amt)}")
    print(f"Distinct charters with charges: {distinct_charters:,}")
    
    # Sample charges
    print("\nSample charter_charges (first 5):")
    cur.execute("""
    SELECT charge_id, charter_id, charge_type, amount, description
    FROM charter_charges
    LIMIT 5
    """)
    for row in cur.fetchall():
        print(f"  {row}")
else:
    print("charter_charges table does not exist")

# 4. Check payment_key patterns
print("\n4. PAYMENT KEY PATTERNS")
print("-" * 100)

cur.execute("""
SELECT 
  CASE 
    WHEN payment_key IS NULL THEN 'NULL'
    WHEN payment_key LIKE 'LMSDEP:%' THEN 'LMSDEP (LMS Deposit)'
    WHEN payment_key LIKE '00%' THEN 'Numeric Key (0000000)'
    WHEN payment_key LIKE 'BTX:%' THEN 'BTX (Banking Transaction)'
    WHEN payment_key LIKE 'QBO:%' THEN 'QBO (QuickBooks Online)'
    ELSE 'Other'
  END AS key_pattern,
  COUNT(*) AS count,
  SUM(amount) AS total_amount,
  COUNT(CASE WHEN amount = 0 THEN 1 END) AS zero_amount_count
FROM payments
GROUP BY key_pattern
ORDER BY COUNT(*) DESC
""")

print(f"{'Pattern':<30} {'Count':>10} {'Total $':>15} {'Zero $':>10}")
print("-" * 70)
for pattern, cnt, amt, zero_cnt in cur.fetchall():
    print(f"{pattern:<30} {cnt:>10,} {fmt_money(amt):>15} {zero_cnt:>10,}")

# 5. Check LMS import - are payments imported with $0 as placeholders?
print("\n5. SAMPLE ZERO-AMOUNT PAYMENTS WITH RESERVE NUMBERS")
print("-" * 100)

cur.execute("""
SELECT payment_id, amount, payment_date, payment_method, reserve_number, payment_key
FROM payments
WHERE amount = 0 
  AND reserve_number IS NOT NULL
LIMIT 10
""")

print(f"{'ID':<8} {'Amount':>10} {'Date':<12} {'Method':<15} {'Reserve':<8} {'Key':<20}")
print("-" * 80)
for row in cur.fetchall():
    pid, amt, dt, method, res, key = row
    print(f"{pid:<8} {fmt_money(amt):>10} {str(dt):<12} {str(method or 'NULL'):<15} {str(res):<8} {str(key or 'NULL'):<20}")

# 6. Check if charters table has payment history/audit columns
print("\n6. CHARTERS TABLE PAYMENT-RELATED COLUMNS")
print("-" * 100)

cur.execute("""
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'charters'
  AND (column_name LIKE '%pay%' 
       OR column_name LIKE '%amount%'
       OR column_name LIKE '%balance%'
       OR column_name LIKE '%deposit%')
ORDER BY ordinal_position
""")

print("Payment-related columns in charters table:")
for col, dtype in cur.fetchall():
    print(f"  {col:<30} {dtype}")

# 7. Sample charter with discrepancy - check all related records
print("\n7. COMPREHENSIVE CHECK: Charter 14039 (Case 1 from earlier)")
print("-" * 100)

charter_id = 14039

# Check if there's a charter_payments or similar join table
cur.execute("""
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('charter_payments', 'charter_payment_links', 'payment_applications')
""")

join_tables = cur.fetchall()
if join_tables:
    print(f"Found join tables: {[t[0] for t in join_tables]}")
    for (tbl,) in join_tables:
        cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE charter_id = %s", (charter_id,))
        cnt = cur.fetchone()[0]
        print(f"  {tbl}: {cnt} rows for charter {charter_id}")
else:
    print("No charter_payments/charter_payment_links tables found")

# 8. Check if paid_amount is computed or stored
print("\n8. PAID_AMOUNT FIELD ANALYSIS")
print("-" * 100)

cur.execute("""
SELECT 
  COUNT(*) AS total_charters,
  COUNT(CASE WHEN paid_amount IS NOT NULL THEN 1 END) AS has_paid_amount,
  COUNT(CASE WHEN paid_amount > 0 THEN 1 END) AS positive_paid_amount,
  SUM(paid_amount) AS total_paid,
  AVG(paid_amount) AS avg_paid
FROM charters
""")

total_c, has_paid, pos_paid, total_paid_sum, avg_paid = cur.fetchone()

print(f"Total charters: {total_c:,}")
print(f"Charters with paid_amount field populated: {has_paid:,}")
print(f"Charters with paid_amount > 0: {pos_paid:,}")
print(f"Sum of all charter.paid_amount: {fmt_money(total_paid_sum)}")
print(f"Average paid_amount (non-zero): {fmt_money(avg_paid)}")

print("\nCONCLUSION:")
print("If most payments.amount = $0, then:")
print("  → payments table contains metadata/references only")
print("  → charter.paid_amount is imported from LMS or computed from other tables")
print("  → Need to identify the true payment transaction table")

cur.close()
conn.close()

print("\n" + "=" * 100)
print("INVESTIGATION COMPLETE")
print("=" * 100)
