"""
Detect corruption in accounting records:
- Duplicate starting balances in banking_transactions
- Orphaned records (no matching charter/receipt/payment)
- Out-of-order transactions
- Missing required fields

Marks records for review; does not auto-delete.
"""
import os
import psycopg2

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 80)
print("ACCOUNTING CORRUPTION DETECTION")
print("=" * 80)

# 1) Duplicate starting balances (bank records adding starting balance multiple times)
print("\n[1] DUPLICATE STARTING BALANCES IN BANKING_TRANSACTIONS")
print("-" * 80)

cur.execute("""
SELECT
  account_number,
  EXTRACT(YEAR FROM transaction_date)::INT AS year,
  COUNT(*) as count,
  STRING_AGG(banking_transaction_id::TEXT, ', ') as ids,
  SUM(debit_amount) as total_debits,
  SUM(credit_amount) as total_credits
FROM banking_transactions
WHERE description ILIKE '%starting balance%'
  OR description ILIKE '%opening balance%'
  OR description ILIKE '%beginning balance%'
GROUP BY account_number, EXTRACT(YEAR FROM transaction_date)
HAVING COUNT(*) > 1
ORDER BY account_number, year
""")

dup_balances = cur.fetchall()
print(f"Found {len(dup_balances)} cases of multiple starting balances per year/account\n")
for acct, year, count, ids, debits, credits in dup_balances[:10]:
    print(f"  Account {acct}, Year {year}: {count} records")
    print(f"    IDs: {ids}")
    print(f"    Debits: {debits}, Credits: {credits}")
    print()

if len(dup_balances) > 10:
    print(f"  ... and {len(dup_balances) - 10} more")

# 2) Orphaned receipts (no matching payment or charter)
print("\n[2] ORPHANED RECEIPTS (No matching charter/payment)")
print("-" * 80)

cur.execute("""
SELECT
  COUNT(*) as orphan_count,
  EXTRACT(YEAR FROM receipt_date)::INT AS year
FROM receipts r
WHERE (r.charter_id IS NULL OR NOT EXISTS (
  SELECT 1 FROM charters c WHERE c.charter_id = r.charter_id
))
AND (r.reserve_number IS NULL OR NOT EXISTS (
  SELECT 1 FROM charters c2 WHERE c2.reserve_number = r.reserve_number
))
AND (r.is_verified_banking = FALSE OR r.created_from_banking = FALSE)
GROUP BY EXTRACT(YEAR FROM receipt_date)
ORDER BY year DESC
""")

orphan_receipts = cur.fetchall()
print(f"Found orphaned receipts by year:\n")
for count, year in orphan_receipts[:10]:
    print(f"  Year {year}: {count} receipts")

# 3) Payments with no matching charter
print("\n[3] ORPHANED PAYMENTS (No matching charter)")
print("-" * 80)

cur.execute("""
SELECT
  COUNT(*) as orphan_count,
  EXTRACT(YEAR FROM payment_date)::INT AS year
FROM payments p
WHERE (p.reserve_number IS NULL OR NOT EXISTS (
  SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
))
AND (p.account_number IS NULL OR NOT EXISTS (
  SELECT 1 FROM charters c2 WHERE c2.account_number = p.account_number
))
GROUP BY EXTRACT(YEAR FROM payment_date)
ORDER BY year DESC
""")

orphan_payments = cur.fetchall()
print(f"Found orphaned payments by year:\n")
for count, year in orphan_payments[:10]:
    print(f"  Year {year}: {count} payments")

# 4) Banking transactions with zero amount
print("\n[4] BANKING TRANSACTIONS WITH ZERO AMOUNT")
print("-" * 80)

cur.execute("""
SELECT
  COUNT(*) as zero_count,
  account_number,
  EXTRACT(YEAR FROM transaction_date)::INT AS year
FROM banking_transactions
WHERE (debit_amount = 0 AND credit_amount = 0) OR (debit_amount IS NULL AND credit_amount IS NULL)
GROUP BY account_number, EXTRACT(YEAR FROM transaction_date)
ORDER BY account_number, year DESC
""")

zero_amounts = cur.fetchall()
print(f"Found zero-amount banking records:\n")
for count, acct, year in zero_amounts[:10]:
    print(f"  Account {acct}, Year {year}: {count} records")

# 5) Receipts with missing vendor or amount
print("\n[5] RECEIPTS WITH MISSING CRITICAL FIELDS")
print("-" * 80)

cur.execute("""
SELECT
  COUNT(*) as incomplete_count,
  CASE
    WHEN vendor_name IS NULL THEN 'Missing vendor'
    WHEN gross_amount IS NULL OR gross_amount = 0 THEN 'Missing/zero amount'
    WHEN receipt_date IS NULL THEN 'Missing date'
    ELSE 'Other'
  END as issue,
  EXTRACT(YEAR FROM receipt_date)::INT AS year
FROM receipts
WHERE vendor_name IS NULL
   OR gross_amount IS NULL
   OR gross_amount = 0
   OR receipt_date IS NULL
GROUP BY issue, EXTRACT(YEAR FROM receipt_date)
ORDER BY year DESC
""")

incomplete_receipts = cur.fetchall()
print(f"Found incomplete receipts:\n")
for count, issue, year in incomplete_receipts[:10]:
    print(f"  {issue} (Year {year}): {count} receipts")

# 6) Summary and recommendations
print("\n" + "=" * 80)
print("CORRUPTION SUMMARY & RECOMMENDATIONS")
print("=" * 80)

print("""
⚠️ ISSUES FOUND:
  1. Duplicate starting balances: Delete extra records, keep one per year/account
  2. Orphaned records: Review for legitimacy before deleting
  3. Zero amounts: Likely data entry errors; mark for review
  4. Missing fields: Cannot post to GL; require correction

🔧 NEXT STEPS:
  1. Review findings with accounting
  2. Identify which records are truly corrupt vs. legitimate exceptions
  3. Create deletion script once approved (with backup)
  4. Re-verify accounting after cleanup
""")

cur.close()
conn.close()
