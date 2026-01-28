"""
Check whether charters with charges but no payments (not cancelled) have refunds linked to them.

Outputs:
- Total no-payment charters (definition below)
- Number and percent that have at least one linked refund (via charter_id or reserve_number)
- Total refund rows and sum of refund amounts for those charters
- Sample list of up to 25 charters with refunds (with refund_count and refund_sum)
- Sample list of up to 10 charters without refunds (for spot-check)

Definition (no-payment charters):
- COALESCE(paid_amount,0) = 0
- (COALESCE(total_amount_due,0) > 0 OR COALESCE(balance,0) > 0)
- Not cancelled (cancelled is false/null, or status not like 'cancel%')
"""
import psycopg2


def get_conn():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )


def get_cancel_filter(cur):
    cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name='charters'
    """
    )
    cols = {r[0] for r in cur.fetchall()}
    if 'cancelled' in cols:
        return "AND (cancelled IS NULL OR cancelled = FALSE)"
    if 'status' in cols:
        return "AND (status IS NULL OR status NOT ILIKE 'cancel%')"
    return ""


print("=" * 100)
print("NO-PAYMENT CHARTERS: REFUND LINK CHECK")
print("=" * 100)

conn = get_conn()
cur = conn.cursor()

cancel_filter = get_cancel_filter(cur)

# Build a temporary scope of no-payment charters
cur.execute(f"""
WITH no_pay AS (
  SELECT charter_id, reserve_number, charter_date, client_id,
         COALESCE(total_amount_due,0) AS total_due,
         COALESCE(paid_amount,0) AS paid,
         COALESCE(balance,0) AS balance,
         status
  FROM charters
  WHERE COALESCE(paid_amount,0) = 0
    AND (COALESCE(total_amount_due,0) > 0 OR COALESCE(balance,0) > 0)
    {cancel_filter}
)
SELECT COUNT(*) FROM no_pay
""")
row = cur.fetchone()
no_pay_total = row[0] if row else 0
print(f"Total no-payment charters: {no_pay_total}")

# How many of those have any refund linked
cur.execute(f"""
WITH no_pay AS (
  SELECT charter_id, reserve_number
  FROM charters
  WHERE COALESCE(paid_amount,0) = 0
    AND (COALESCE(total_amount_due,0) > 0 OR COALESCE(balance,0) > 0)
    {cancel_filter}
)
SELECT COUNT(*)
FROM no_pay n
WHERE EXISTS (
  SELECT 1 FROM charter_refunds r
  WHERE (r.charter_id IS NOT NULL AND r.charter_id = n.charter_id)
     OR (r.reserve_number IS NOT NULL AND n.reserve_number IS NOT NULL AND r.reserve_number = n.reserve_number)
)
""")
row = cur.fetchone()
with_refunds = row[0] if row else 0
pct = (with_refunds / no_pay_total * 100.0) if no_pay_total else 0.0
print(f"No-payment charters with at least one refund: {with_refunds} ({pct:.2f}%)")

# Total refund rows and sum of refund amounts among those charters
cur.execute(f"""
WITH no_pay AS (
  SELECT charter_id, reserve_number
  FROM charters
  WHERE COALESCE(paid_amount,0) = 0
    AND (COALESCE(total_amount_due,0) > 0 OR COALESCE(balance,0) > 0)
    {cancel_filter}
)
SELECT COUNT(*) AS refund_rows, COALESCE(SUM(r.amount),0) AS refund_sum
FROM charter_refunds r
JOIN no_pay n
  ON (r.charter_id IS NOT NULL AND r.charter_id = n.charter_id)
  OR (r.reserve_number IS NOT NULL AND n.reserve_number IS NOT NULL AND r.reserve_number = n.reserve_number)
""")
refund_rows, refund_sum = cur.fetchone()
print(f"Refund rows linked to no-payment charters: {refund_rows}")
print(f"Total refund amount on those charters: ${float(refund_sum or 0):,.2f}")

# Sample: top 25 no-payment charters WITH refunds
print("\nTop 25 no-payment charters WITH refunds:")
cur.execute(f"""
WITH no_pay AS (
  SELECT charter_id, reserve_number, charter_date, client_id
  FROM charters
  WHERE COALESCE(paid_amount,0) = 0
    AND (COALESCE(total_amount_due,0) > 0 OR COALESCE(balance,0) > 0)
    {cancel_filter}
),
agg AS (
  SELECT n.charter_id,
         COUNT(r.id) AS refund_count,
         SUM(r.amount) AS refund_sum
  FROM no_pay n
  JOIN charter_refunds r
    ON (r.charter_id IS NOT NULL AND r.charter_id = n.charter_id)
    OR (r.reserve_number IS NOT NULL AND n.reserve_number IS NOT NULL AND r.reserve_number = n.reserve_number)
  GROUP BY n.charter_id
)
SELECT n.charter_id, n.reserve_number, n.charter_date, n.client_id,
       a.refund_count, a.refund_sum
FROM no_pay n
JOIN agg a ON a.charter_id = n.charter_id
ORDER BY a.refund_sum DESC NULLS LAST, a.refund_count DESC
LIMIT 25
""")
rows = cur.fetchall()
if rows:
    print(f"{'CharterID':<10} {'Reserve':<8} {'Date':<10} {'Client':<8} {'Refunds':>8} {'RefundSum':>12}")
    print('-'*70)
    for r in rows:
        cid, res, dt, client, rcnt, rsum = r
        print(f"{cid:<10} {str(res or ''):<8} {dt} {str(client or ''):<8} {rcnt:8d} ${float(rsum or 0):11,.2f}")
else:
    print("(none)")

# Sample: 10 no-payment charters WITHOUT refunds
print("\nSample 10 no-payment charters WITHOUT refunds:")
cur.execute(f"""
WITH no_pay AS (
  SELECT charter_id, reserve_number, charter_date, client_id
  FROM charters
  WHERE COALESCE(paid_amount,0) = 0
    AND (COALESCE(total_amount_due,0) > 0 OR COALESCE(balance,0) > 0)
    {cancel_filter}
)
SELECT n.charter_id, n.reserve_number, n.charter_date, n.client_id
FROM no_pay n
WHERE NOT EXISTS (
  SELECT 1 FROM charter_refunds r
  WHERE (r.charter_id IS NOT NULL AND r.charter_id = n.charter_id)
     OR (r.reserve_number IS NOT NULL AND n.reserve_number IS NOT NULL AND r.reserve_number = n.reserve_number)
)
ORDER BY n.charter_date DESC, n.charter_id DESC
LIMIT 10
""")
rows = cur.fetchall()
if rows:
    print(f"{'CharterID':<10} {'Reserve':<8} {'Date':<10} {'Client':<8}")
    print('-'*50)
    for r in rows:
        cid, res, dt, client = r
        print(f"{cid:<10} {str(res or ''):<8} {dt} {str(client or ''):<8}")
else:
    print("(none)")

cur.close(); conn.close()

print("\n" + "=" * 100)
print("CHECK COMPLETE")
print("=" * 100)
