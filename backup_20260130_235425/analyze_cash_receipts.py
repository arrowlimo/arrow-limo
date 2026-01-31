"""
Find all receipts with cash payment method and categorize them.
This follows the QuickBooks approach for cash payments.
"""

import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REDACTED***",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

print("=" * 80)
print("CASH PAYMENT RECEIPTS ANALYSIS")
print("=" * 80)
print()

# Find all receipts with cash payment method
print("Step 1: Finding cash payment receipts...")
print()

# Check different payment method variations
cash_patterns = ['cash', 'Cash', 'CASH', 'Petty Cash', 'petty cash']

for pattern in cash_patterns:
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE payment_method = %s
        OR pay_method = %s
        OR canonical_pay_method = %s
    """, (pattern, pattern, pattern))
    
    count, amount = cur.fetchone()
    if count and count > 0:
        print(f"  Payment method '{pattern}': {count:,} receipts, ${amount:,.2f}")

print()

# Get all unique payment methods containing 'cash'
cur.execute("""
    SELECT DISTINCT 
        COALESCE(payment_method, pay_method, canonical_pay_method) as method,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE LOWER(COALESCE(payment_method, pay_method, canonical_pay_method, '')) LIKE '%cash%'
    GROUP BY method
    ORDER BY count DESC
""")

print("All payment methods containing 'cash':")
results = cur.fetchall()
total_cash_count = 0
total_cash_amount = 0

for method, count, amount in results:
    if amount:
        print(f"  {method:30} {count:6,} receipts  ${amount:12,.2f}")
        total_cash_count += count
        total_cash_amount += float(amount) if amount else 0
    else:
        print(f"  {method:30} {count:6,} receipts  (no amount)")

print()
print(f"Total cash receipts: {total_cash_count:,}")
print(f"Total cash amount: ${total_cash_amount:,.2f}")
print()

# Sample cash receipts
print("=" * 80)
print("SAMPLE CASH RECEIPTS")
print("=" * 80)
print()

cur.execute("""
    SELECT 
        id,
        receipt_date,
        vendor_name,
        description,
        gross_amount,
        expense_account,
        payment_method,
        pay_method,
        canonical_pay_method
    FROM receipts
    WHERE LOWER(COALESCE(payment_method, pay_method, canonical_pay_method, '')) LIKE '%cash%'
    ORDER BY gross_amount DESC NULLS LAST
    LIMIT 20
""")

for row in cur.fetchall():
    receipt_id, date, vendor, desc, amount, exp_acct, pm1, pm2, pm3 = row
    pay_method = pm1 or pm2 or pm3 or 'None'
    print(f"{receipt_id:8} | {date} | {pay_method:15} | ${amount:10,.2f} | {vendor or 'No vendor'}")
    if desc:
        print(f"         | {desc[:70]}")
    print()

# Check what expense accounts they have
print("=" * 80)
print("CASH RECEIPTS BY EXPENSE ACCOUNT")
print("=" * 80)
print()

cur.execute("""
    SELECT 
        expense_account,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE LOWER(COALESCE(payment_method, pay_method, canonical_pay_method, '')) LIKE '%cash%'
    GROUP BY expense_account
    ORDER BY count DESC
""")

for acct, count, amount in cur.fetchall():
    if amount:
        print(f"  {acct or '(no account)':40} {count:6,} receipts  ${amount:12,.2f}")
    else:
        print(f"  {acct or '(no account)':40} {count:6,} receipts  (no amount)")

print()
print("=" * 80)
print("CATEGORIZATION PLAN")
print("=" * 80)
print()

print("QuickBooks approach for cash payments:")
print("  - Cash payments are already categorized by their expense_account")
print("  - We just need to ensure they have the correct GL categorization")
print("  - payment_method = 'Cash' is already set by QuickBooks")
print()

print("Next steps:")
print("  1. Verify all cash receipts have proper expense_account")
print("  2. Check for any cash receipts without categorization")
print("  3. Update canonical_pay_method to 'Cash' for consistency")
print("  4. Link to GL accounts based on expense_account")

# Find cash receipts without expense account
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE LOWER(COALESCE(payment_method, pay_method, canonical_pay_method, '')) LIKE '%cash%'
    AND (expense_account IS NULL OR expense_account = '')
""")

no_acct_count, no_acct_amount = cur.fetchone()
if no_acct_count and no_acct_count > 0:
    print()
    print(f"[WARN]  WARNING: {no_acct_count:,} cash receipts without expense_account (${no_acct_amount:,.2f})")
else:
    print()
    print(f"✓ All cash receipts have expense_account assigned")

cur.close()
conn.close()
