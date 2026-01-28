"""
Investigate negative adjustments where charter_payments < charter.paid_amount.

This could indicate:
1. Refunds recorded in charter.paid_amount but not in charter_payments
2. Payment reversals or corrections
3. Data from multiple sources not fully captured in charter_payments
4. Legacy data imported differently

We need to understand these before proceeding with sync.
"""
import psycopg2


def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***",
    )


def fmt_money(v):
    return f"${float(v or 0):,.2f}"


print("=" * 100)
print("NEGATIVE ADJUSTMENT INVESTIGATION")
print("=" * 100)

conn = get_conn()
cur = conn.cursor()

# Get charters where charter_payments < paid_amount
cur.execute("""
WITH cp_sums AS (
  SELECT 
    charter_id::integer AS cid,
    SUM(amount) AS cp_total,
    COUNT(*) AS cp_count
  FROM charter_payments
  WHERE reserve_number IS NOT NULL 
    AND charter_id ~ '^[0-9]+$'
  GROUP BY charter_id::integer
)
SELECT 
  c.charter_id,
  c.reserve_number,
  c.charter_date,
  COALESCE(c.paid_amount, 0) AS paid_amt,
  COALESCE(c.total_amount_due, 0) AS total_due,
  COALESCE(c.balance, 0) AS balance,
  cp.cp_total AS cp_sum,
  COALESCE(c.paid_amount, 0) - cp.cp_total AS excess,
  cp.cp_count AS pay_count
FROM charters c
JOIN cp_sums cp ON cp.cid = c.charter_id
WHERE c.paid_amount > cp.cp_total + 0.02
ORDER BY (c.paid_amount - cp.cp_total) DESC
LIMIT 50
""")

negative_adj = cur.fetchall()

print(f"\nFound {len(negative_adj)} charters where paid_amount > charter_payments sum")
print("\nTop 50 cases:")
print(f"{'Charter':<8} {'Reserve':<8} {'Date':<12} {'Paid$':>12} {'CP_Sum$':>12} {'Excess':>12} {'TotalDue':>12} {'Bal':>12} {'#Pay':>5}")
print("-" * 115)

for cid, res, dt, paid, total, bal, cp_sum, excess, pcount in negative_adj:
    print(f"{cid:<8} {str(res or ''):<8} {str(dt):<12} {fmt_money(paid):>12} {fmt_money(cp_sum):>12} {fmt_money(excess):>12} {fmt_money(total):>12} {fmt_money(bal):>12} {pcount:>5}")

# Check if these charters have refunds
print("\n" + "=" * 100)
print("CHECKING FOR REFUNDS ON THESE CHARTERS")
print("=" * 100)

cur.execute("""
WITH cp_sums AS (
  SELECT 
    charter_id::integer AS cid,
    SUM(amount) AS cp_total
  FROM charter_payments
  WHERE reserve_number IS NOT NULL 
    AND charter_id ~ '^[0-9]+$'
  GROUP BY charter_id::integer
),
negative_adj_charters AS (
  SELECT c.charter_id, c.reserve_number, c.paid_amount, cp.cp_total
  FROM charters c
  JOIN cp_sums cp ON cp.cid = c.charter_id
  WHERE c.paid_amount > cp.cp_total + 0.02
)
SELECT 
  n.charter_id,
  n.reserve_number,
  n.paid_amount,
  n.cp_total,
  COUNT(r.id) AS refund_count,
  SUM(r.amount) AS refund_sum
FROM negative_adj_charters n
LEFT JOIN charter_refunds r ON (r.charter_id::integer = n.charter_id OR r.reserve_number = n.reserve_number)
GROUP BY n.charter_id, n.reserve_number, n.paid_amount, n.cp_total
HAVING COUNT(r.id) > 0
ORDER BY SUM(r.amount) DESC NULLS LAST
LIMIT 20
""")

refund_cases = cur.fetchall()

if refund_cases:
    print(f"\n{len(refund_cases)} of these charters have refunds:")
    print(f"{'Charter':<8} {'Reserve':<8} {'Paid$':>12} {'CP_Sum$':>12} {'Refunds':>8} {'Refund$':>12}")
    print("-" * 70)
    for cid, res, paid, cp_sum, ref_cnt, ref_sum in refund_cases:
        print(f"{cid:<8} {str(res or ''):<8} {fmt_money(paid):>12} {fmt_money(cp_sum):>12} {ref_cnt:>8} {fmt_money(ref_sum):>12}")
else:
    print("\nNone of these charters have refunds in charter_refunds table")

# Check if payments table has additional entries
print("\n" + "=" * 100)
print("CHECKING PAYMENTS TABLE FOR ADDITIONAL ENTRIES")
print("=" * 100)

cur.execute("""
WITH cp_sums AS (
  SELECT 
    charter_id::integer AS cid,
    SUM(amount) AS cp_total
  FROM charter_payments
  WHERE reserve_number IS NOT NULL 
    AND charter_id ~ '^[0-9]+$'
  GROUP BY charter_id::integer
),
negative_adj_charters AS (
  SELECT c.charter_id, c.reserve_number, c.paid_amount, cp.cp_total
  FROM charters c
  JOIN cp_sums cp ON cp.cid = c.charter_id
  WHERE c.paid_amount > cp.cp_total + 0.02
  LIMIT 10
)
SELECT 
  n.charter_id,
  n.reserve_number,
  n.paid_amount,
  n.cp_total,
  COUNT(p.payment_id) AS payment_rows,
  SUM(CASE WHEN p.amount > 0 THEN p.amount ELSE 0 END) AS positive_sum
FROM negative_adj_charters n
LEFT JOIN payments p ON (p.charter_id = n.charter_id OR p.reserve_number = n.reserve_number)
GROUP BY n.charter_id, n.reserve_number, n.paid_amount, n.cp_total
""")

payment_check = cur.fetchall()

print(f"\nChecking payments table for first 10 negative adjustment charters:")
print(f"{'Charter':<8} {'Reserve':<8} {'Paid$':>12} {'CP_Sum$':>12} {'Pay_Rows':>10} {'Pay_Sum$':>12}")
print("-" * 75)
for cid, res, paid, cp_sum, prows, psum in payment_check:
    print(f"{cid:<8} {str(res or ''):<8} {fmt_money(paid):>12} {fmt_money(cp_sum):>12} {prows:>10} {fmt_money(psum):>12}")

# Deep dive on Charter 16187 (largest negative adjustment)
print("\n" + "=" * 100)
print("DEEP DIVE: Charter 16187 (paid_amount $3,852, charter_payments $93.75)")
print("=" * 100)

charter_id = 16187

cur.execute("""
SELECT charter_id, reserve_number, charter_date, paid_amount, total_amount_due, balance, status
FROM charters
WHERE charter_id = %s
""", (charter_id,))

cid, res, dt, paid, total, bal, status = cur.fetchone()
print(f"\nCharter Details:")
print(f"  Reserve: {res}, Date: {dt}")
print(f"  Paid: {fmt_money(paid)}, Total Due: {fmt_money(total)}, Balance: {fmt_money(bal)}")
print(f"  Status: {status}")

cur.execute("""
SELECT payment_id, charter_id, amount, payment_date, payment_method, payment_key
FROM charter_payments
WHERE charter_id = %s
ORDER BY payment_date
""", (str(charter_id),))

cp_rows = cur.fetchall()
print(f"\ncharter_payments entries ({len(cp_rows)}):")
for pid, cid, amt, pdate, method, key in cp_rows:
    print(f"  {pid}: {fmt_money(amt)} on {pdate} ({method or 'NULL'})")

cur.execute("""
SELECT payment_id, amount, payment_date, payment_method, payment_key, reserve_number
FROM payments
WHERE charter_id = %s OR reserve_number = %s
ORDER BY payment_date
""", (charter_id, res))

pay_rows = cur.fetchall()
print(f"\npayments table entries ({len(pay_rows)}):")
for pid, amt, pdate, method, key, pres in pay_rows:
    print(f"  {pid}: {fmt_money(amt)} on {pdate} (method: {method or 'NULL'}, key: {key or 'NULL'})")

cur.close()
conn.close()

print("\n" + "=" * 100)
print("INVESTIGATION COMPLETE")
print("=" * 100)
print("\nCONCLUSION:")
print("If charter.paid_amount includes payments not in charter_payments,")
print("we need to decide:")
print("  1. Trust charter_payments as source of truth (may lose some payment history)")
print("  2. Preserve charter.paid_amount where it's higher (may not match detail)")
print("  3. Investigate and migrate missing payments to charter_payments first")
