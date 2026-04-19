#!/usr/bin/env python3
"""
CLARIFICATION: Revenue vs. Banking Deposits

Revenue = charter_payments only (customer paid for charter service)
Internal transfers = cash deposits NOT attached to charter_payments

This script verifies what is and isn't revenue.
"""

import psycopg2

DB_HOST = 'localhost'
DB_PORT = 5432
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = 'ArrowLimousine'

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("\n" + "="*90)
print("REVENUE VS. BANKING DEPOSITS - 2012 CLARIFICATION")
print("="*90)

print("""
Business Rule:
  REVENUE = charter_payments.amount (customer paid for charter service)
  NOT REVENUE = cash deposits to bank that are NOT charter_payments
  
  Examples of NOT REVENUE:
    - Owner deposits (personal cash injected)
    - Shareholder loans
    - Line of credit draws
    - Bank transfers between accounts
    - Any OTHER cash that's not a customer payment for a charter
""")

# 1. All charter_payments in 2012 (regardless of when)
print("\n=== REVENUE: Charter Payments (payments BY customers FOR charters) ===\n")

query1 = """
SELECT 
    COUNT(*) as total_payment_records,
    COUNT(CASE WHEN EXTRACT(YEAR FROM payment_date) = 2012 THEN 1 END) as paid_in_2012,
    COALESCE(SUM(amount), 0) as total_all_years,
    COALESCE(SUM(CASE WHEN EXTRACT(YEAR FROM payment_date) = 2012 THEN amount ELSE 0 END), 0) as paid_2012
FROM charter_payments;
"""

cur.execute(query1)
total_recs, paid_2012_count, total_all, paid_2012_amt = cur.fetchone()

print(f"All charter_payments (all years):           {total_recs:>10} records, ${float(total_all):>12,.2f} TOTAL")
print(f"Charter_payments with payment_date in 2012: {paid_2012_count:>10} records, ${float(paid_2012_amt):>12,.2f} ← 2012 REVENUE")

# 2. Break down by payment method
print(f"\n2012 Charter Payments by Payment Method:")
query2 = """
SELECT 
    COALESCE(LOWER(payment_method), 'unknown') as method,
    COUNT(*) as count,
    COALESCE(SUM(amount), 0) as total
FROM charter_payments
WHERE EXTRACT(YEAR FROM payment_date) = 2012
GROUP BY LOWER(payment_method)
ORDER BY total DESC;
"""

cur.execute(query2)
methods = cur.fetchall()
for method, cnt, amt in methods:
    print(f"  {method:<20} {cnt:>4} payments  ${float(amt):>12,.2f}")

print(f"\n  ✓ ALL of these are REVENUE (regardless of payment method)")
print(f"    Because customer paid for a charter service")

# 3. Check banking deposits
print(f"\n=== NOT REVENUE: Banking Deposits (may include non-revenue items) ===\n")

query3 = """
SELECT 
    COUNT(*) as total_deposits,
    COALESCE(SUM(credit_amount), 0) as total_credits
FROM banking_transactions
WHERE EXTRACT(YEAR FROM transaction_date) = 2012
  AND credit_amount > 0;
"""

cur.execute(query3)
total_dep, total_cred = cur.fetchone()

print(f"Banking transaction deposits in 2012:       {total_dep} credits, ${float(total_cred):,.2f}")
print(f"  - These may include: owner deposits, loans, transfers, etc.")
print(f"  - NOT all are customer payment revenue")
print(f"  - Many are: shareholder loans, account transfers, non-customer deposits")

# 4. The key distinction
print(f"\n" + "="*90)
print("KEY DISTINCTION FOR T2:")
print("="*90)

print(f"""
  2012 REVENUE (for T2 reporting) = ${float(paid_2012_amt):,.2f}
  
  Source: charter_payments WHERE EXTRACT(YEAR FROM payment_date) = 2012
  
  This is:
    ✓ Cash received from customers for charter services
    ✓ Cash basis (when payment was received, not when invoice issued)
    ✓ Includes: cash, cheque, credit card, e-transfer, trade, etc.
    ✓ The ONLY revenue that goes on the T2 return
  
  Banking deposits that are NOT in charter_payments:
    ✗ Owner deposits (cash owner put in)
    ✗ Shareholder loans (borrowed money, not revenue)
    ✗ Line of credit draws
    ✗ Account transfers
    → These are NOT revenue
    → These are internal transfers or financing


  To record in income_ledger for T2:
  
  INSERT INTO income_ledger
  SELECT 
    id as payment_id,
    'charter_payments' as source_system,
    payment_date as transaction_date,
    2012 as fiscal_year,
    EXTRACT(QUARTER FROM payment_date)::int as fiscal_quarter,
    'Operating Revenue' as revenue_category,
    'Charter Services' as revenue_subcategory,
    amount as gross_amount,
    (amount * 5 / 105) as gst_collected,
    (amount - (amount * 5 / 105)) as net_amount,
    true as is_taxable,
    'AB' as tax_province,
    -- ... other fields from join to charters
  FROM charter_payments
  WHERE EXTRACT(YEAR FROM payment_date) = 2012
""")

print(f"\n" + "="*90)
print(f"2012 T2 REVENUE SUMMARY:")
print("="*90)
print(f"""
  Total Revenue: ${float(paid_2012_amt):,.2f}
  Method: Charter payments received (cash basis)
  GST payable: ${float(paid_2012_amt * 5 / 105):,.2f}
  
  This ONLY goes in income_ledger.
  Banking deposits that are personal/loan/transfers do NOT go in income_ledger.
""")

cur.close()
conn.close()
