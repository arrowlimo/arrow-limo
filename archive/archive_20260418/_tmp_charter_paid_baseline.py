import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

print("=" * 70)
print("BASELINE CHARTER: 005362  (charter_id=4314, 2012-07-21, $1,234.60)")
print("=" * 70)

# 1. Stored columns in charters
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due,
           rate, paid_amount, amount_paid, balance_owing, balance, payment_status
    FROM charters WHERE reserve_number = '005362'
""")
row = cur.fetchone()
print("\ncharters table columns relevant to payment:")
print(f"  charter_id        = {row[0]}")
print(f"  reserve_number    = {row[1]}")
print(f"  charter_date      = {row[2]}")
print(f"  total_amount_due  = {row[3]}  (used as total in UI)")
print(f"  rate              = {row[4]}  (used as 'charter_charge')")
print(f"  paid_amount       = {row[5]}  <-- CODE READS THIS (WRONG - always 0)")
print(f"  amount_paid       = {row[6]}  <-- CORRECT column (trigger-synced)")
print(f"  balance_owing     = {row[7]}")
print(f"  balance           = {row[8]}")
print(f"  payment_status    = {row[9]}")

# 2. payments table for this reserve
print("\n--- payments table WHERE reserve_number='005362' ---")
cur.execute("""
    SELECT payment_id, reserve_number, charter_id, amount, payment_method,
           payment_date, status, reference_number, is_deposited
    FROM payments WHERE reserve_number = '005362'
""")
pay_rows = cur.fetchall()
print(f"  {len(pay_rows)} row(s) found")
for p in pay_rows:
    print(f"  payment_id={p[0]}  res={p[1]}  charter_id={p[2]}  amount={p[3]}")
    print(f"    method={p[4]}  date={p[5]}  status={p[6]}  ref={p[7]}  deposited={p[8]}")

# 3. charter_payments table
print("\n--- charter_payments WHERE charter_id='4314' ---")
cur.execute("SELECT id, charter_id, amount, payment_date, payment_method, source FROM charter_payments WHERE charter_id = '4314'")
cp_rows = cur.fetchall()
print(f"  {len(cp_rows)} row(s) found")
for r in cp_rows:
    print(f"  id={r[0]}  charter_id={r[1]}  amount={r[2]}  date={r[3]}  method={r[4]}  source={r[5]}")

print()
print("=" * 70)
print("SCALE OF BUG: paid_amount=0 vs amount_paid=correct")
print("=" * 70)

cur.execute("SELECT COUNT(*) FROM charters WHERE paid_amount = 0 AND amount_paid > 0")
print(f"  Charters: paid_amount=0.00 BUT amount_paid>0  = {cur.fetchone()[0]:,}  rows affected")

cur.execute("SELECT COUNT(*) FROM payments WHERE reserve_number IS NOT NULL AND reserve_number != ''")
print(f"  payments with reserve_number set            = {cur.fetchone()[0]:,}")

cur.execute("SELECT COUNT(*) FROM payments WHERE (reserve_number IS NULL OR reserve_number = '') AND charter_id IS NOT NULL")
print(f"  payments with NO reserve_number (charter_id only) = {cur.fetchone()[0]:,}")

print()
print("=" * 70)
print("CODE BUG LOCATION: drill_down_widgets.py ~ line 2977")
print("=" * 70)
print("""
  The query reads:
    COALESCE(paid_amount, 0) as paid_from_column        <-- WRONG COLUMN
  Should read:
    COALESCE(amount_paid, 0) as paid_from_column        <-- CORRECT COLUMN

  paid_amount   = always 0.00  (16,592 charters broken)
  amount_paid   = trigger-synced real value  (16,598 charters have data)

  Secondary fallback in code (if paid_from_column==0 and total_paid>0):
    also fails for charters that have payments ONLY linked by charter_id
    (no reserve_number in payments table) because the payments query uses:
    WHERE reserve_number = %s
""")

# Check 005712 from screenshot
print("=" * 70)
print("SCREENSHOT CHARTER: 005712  (charter_id=4677)")
print("=" * 70)
cur.execute("""
    SELECT charter_id, total_amount_due, rate, paid_amount, amount_paid, balance_owing
    FROM charters WHERE reserve_number = '005712'
""")
row2 = cur.fetchone()
print(f"  total_amount_due={row2[1]}  rate={row2[2]}  paid_amount(wrong)={row2[3]}  amount_paid(correct)={row2[4]}")

cur.execute("SELECT payment_id, amount, payment_method, payment_date, reserve_number, charter_id FROM payments WHERE reserve_number='005712' OR charter_id=4677")
pays2 = cur.fetchall()
print(f"  payments rows (by reserve OR charter_id): {len(pays2)}")
for p in pays2:
    print(f"    payment_id={p[0]}  amount={p[1]}  method={p[2]}  date={p[3]}  reserve={p[4]}  charter_id={p[5]}")

conn.close()
print("\nDone.")
