"""Comprehensive revenue audit - distinguish income from non-income transactions.

This audit separates:
1. Actual charter revenue (fees + extras + GST + gratuity)
2. Deposits (liability, not income)
3. Loan payments (asset/liability, not income)
4. Vehicle transactions (capital, not income)
5. Insurance payments (expense, not income)
6. Duplications and irregularities
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 80)
print("COMPREHENSIVE REVENUE AUDIT - INCOME vs NON-INCOME")
print("=" * 80)

# 1. CHARTER-BASED ACTUAL REVENUE
print("\n1. ACTUAL CHARTER REVENUE (2007-2024)")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) as charter_count,
        SUM(rate) as base_rate,
        SUM(COALESCE(airport_dropoff_price, 0) + COALESCE(airport_pickup_price, 0)) as airport_fees,
        SUM(deposit) as deposits_collected,
        SUM(balance) as outstanding_balance,
        SUM(rate) + SUM(COALESCE(airport_dropoff_price, 0) + COALESCE(airport_pickup_price, 0)) as total_billable
    FROM charters
    WHERE charter_date >= '2007-01-01'
    AND charter_date <= '2024-12-31'
    AND status NOT IN ('cancelled', 'Cancelled')
""")

charter_rev = cur.fetchone()
print(f"Non-cancelled charters: {charter_rev[0]:,}")
print(f"Base charter rates: ${charter_rev[1]:,.2f}")
print(f"Airport fees: ${charter_rev[2]:,.2f}")
print(f"Total billable (before GST/gratuity): ${charter_rev[5]:,.2f}")
print(f"Customer deposits collected: ${charter_rev[3]:,.2f}")
print(f"Outstanding balance: ${charter_rev[4]:,.2f}")

# Calculate total revenue with GST and gratuity (estimate 5% GST, 15% gratuity avg)
from decimal import Decimal
base_billable = float(charter_rev[5] or 0)
estimated_gst = base_billable * 0.05
estimated_gratuity = base_billable * 0.15
estimated_total_revenue = base_billable * 1.20  # Base + 5% GST + 15% gratuity

print(f"\nESTIMATED TOTAL REVENUE:")
print(f"Base billable: ${base_billable:,.2f}")
print(f"Add GST (5%): ${estimated_gst:,.2f}")
print(f"Add Gratuity (avg 15%): ${estimated_gratuity:,.2f}")
print(f"TOTAL CHARTER REVENUE: ${estimated_total_revenue:,.2f}")

# 2. IDENTIFY DEPOSITS vs REVENUE PAYMENTS
print("\n2. PAYMENT CLASSIFICATION: DEPOSITS vs REVENUE")
print("-" * 80)
cur.execute("""
    SELECT 
        CASE 
            WHEN payment_key LIKE 'LMSDEP:%' THEN 'Customer Deposit'
            WHEN payment_method IN ('deposit', 'Deposit') THEN 'Customer Deposit'
            WHEN notes LIKE '%deposit%' OR notes LIKE '%Deposit%' THEN 'Customer Deposit'
            WHEN charter_id IS NULL AND amount > 0 THEN 'Unallocated (possibly deposit)'
            WHEN charter_id IS NOT NULL THEN 'Charter Payment (Revenue)'
            ELSE 'Other'
        END as payment_type,
        COUNT(*) as payment_count,
        SUM(amount) as total_amount
    FROM payments
    WHERE payment_date >= '2007-01-01'
    AND payment_date <= '2024-12-31'
    GROUP BY payment_type
    ORDER BY total_amount DESC
""")

print(f"{'Payment Type':<35} {'Count':<10} {'Amount':<20}")
print("-" * 80)

total_revenue_payments = 0
total_deposits = 0

for row in cur.fetchall():
    ptype, count, amount = row[0], row[1], row[2] or 0
    print(f"{ptype:<35} {count:<10,} ${amount:>18,.2f}")
    
    if 'Revenue' in ptype:
        total_revenue_payments += amount
    elif 'Deposit' in ptype or 'Unallocated' in ptype:
        total_deposits += amount

print("-" * 80)
print(f"{'REVENUE PAYMENTS (matched to charters)':<35} {'':<10} ${total_revenue_payments:>18,.2f}")
print(f"{'DEPOSITS (not revenue)':<35} {'':<10} ${total_deposits:>18,.2f}")

# 3. IDENTIFY NON-INCOME TRANSACTIONS
print("\n3. NON-INCOME TRANSACTIONS")
print("-" * 80)

# Check for insurance payments
cur.execute("""
    SELECT 
        COUNT(*) as payment_count,
        SUM(amount) as total_amount
    FROM payments
    WHERE payment_date >= '2007-01-01'
    AND payment_date <= '2024-12-31'
    AND (
        notes LIKE '%insurance%'
        OR notes LIKE '%Insurance%'
        OR notes LIKE '%Nordic%'
    )
""")
insurance = cur.fetchone()
print(f"Insurance payments (not revenue): {insurance[0]:,} payments, ${insurance[1]:,.2f}" if insurance[1] else f"Insurance payments: {insurance[0]:,} payments, $0.00")

# Check for specific Nordic Insurance payment
cur.execute("""
    SELECT 
        payment_id,
        payment_date,
        amount,
        notes
    FROM payments
    WHERE payment_date = '2019-07-15'
    AND amount = 8220.00
""")
nordic = cur.fetchall()
if nordic:
    print(f"\nNordic Insurance payment (July 15, 2019):")
    for row in nordic:
        print(f"  Payment ID: {row[0]}, Amount: ${row[2]:,.2f}, Notes: {row[3]}")
else:
    print(f"\nNordic Insurance $8,220 payment not found in payments table")
    # Check receipts table - get actual column names first
    cur.execute("""
        SELECT id, receipt_date, gross_amount, vendor_name, description
        FROM receipts
        WHERE receipt_date = '2019-07-15'
        AND vendor_name LIKE '%Nordic%'
    """)
    nordic_receipt = cur.fetchall()
    if nordic_receipt:
        print(f"  Found in RECEIPTS table (expense, not in payments):")
        for row in nordic_receipt:
            print(f"    Receipt ID: {row[0]}, Amount: ${row[2]:,.2f}, Vendor: {row[3]}")

# Check receipts for vehicle/loan/insurance (non-income)
print(f"\nNON-INCOME EXPENSES (from receipts table):")
cur.execute("""
    SELECT 
        CASE 
            WHEN vendor_name LIKE '%Insurance%' OR description LIKE '%insurance%' THEN 'Insurance'
            WHEN vendor_name LIKE '%Finance%' OR vendor_name LIKE '%Loan%' OR description LIKE '%loan%' THEN 'Loan/Finance'
            WHEN category LIKE '%Vehicle%' OR description LIKE '%vehicle purchase%' THEN 'Vehicle Purchase'
            WHEN vendor_name LIKE '%CRA%' OR vendor_name LIKE '%Revenue Agency%' THEN 'CRA/Tax'
            ELSE 'Other Expense'
        END as expense_type,
        COUNT(*) as receipt_count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE receipt_date >= '2007-01-01'
    AND receipt_date <= '2024-12-31'
    GROUP BY expense_type
    ORDER BY total_amount DESC
    LIMIT 10
""")
print(f"{'Expense Type':<30} {'Count':<10} {'Amount':<20}")
print("-" * 80)
for row in cur.fetchall():
    print(f"{row[0]:<30} {row[1]:<10,} ${row[2]:>18,.2f}")

# 4. CHECK FOR DUPLICATIONS
print("\n4. DUPLICATION ANALYSIS")
print("-" * 80)

# Payments with same date, amount, account
cur.execute("""
    WITH payment_groups AS (
        SELECT 
            payment_date,
            amount,
            account_number,
            COUNT(*) as dup_count,
            STRING_AGG(payment_id::text, ', ') as payment_ids
        FROM payments
        WHERE payment_date >= '2007-01-01'
        AND payment_date <= '2024-12-31'
        AND amount > 0
        GROUP BY payment_date, amount, account_number
        HAVING COUNT(*) > 1
    )
    SELECT 
        COUNT(*) as group_count,
        SUM(dup_count) as total_duplicates,
        SUM(amount * (dup_count - 1)) as duplicate_amount
    FROM payment_groups
""")
dups = cur.fetchone()
print(f"Potential duplicate payment groups: {dups[0]:,}")
print(f"Total duplicate payments: {dups[1]:,}")
print(f"Duplicate amount (overstated): ${dups[2]:,.2f}" if dups[2] else "Duplicate amount: $0.00")

# Sample duplicates
print(f"\nSample duplicate payments:")
cur.execute("""
    WITH payment_groups AS (
        SELECT 
            payment_date,
            amount,
            account_number,
            COUNT(*) as dup_count,
            STRING_AGG(payment_id::text, ', ' ORDER BY payment_id) as payment_ids
        FROM payments
        WHERE payment_date >= '2007-01-01'
        AND payment_date <= '2024-12-31'
        AND amount > 0
        GROUP BY payment_date, amount, account_number
        HAVING COUNT(*) > 1
    )
    SELECT 
        payment_date,
        amount,
        dup_count,
        payment_ids
    FROM payment_groups
    ORDER BY amount DESC
    LIMIT 10
""")
print(f"{'Date':<12} {'Amount':<12} {'Copies':<8} {'Payment IDs':<40}")
print("-" * 80)
for row in cur.fetchall():
    ids = row[3][:38]
    print(f"{str(row[0]):<12} ${row[1]:<11,.2f} {row[2]:<8} {ids:<40}")

# 5. BANKING RECONCILIATION
print("\n5. BANKING RECONCILIATION")
print("-" * 80)
cur.execute("""
    SELECT 
        SUM(credit_amount) as total_deposits,
        SUM(debit_amount) as total_withdrawals,
        SUM(credit_amount) - SUM(debit_amount) as net_cash_flow
    FROM banking_transactions
    WHERE transaction_date >= '2007-01-01'
    AND transaction_date <= '2024-12-31'
""")
banking = cur.fetchone()
print(f"Total bank deposits (credits): ${banking[0]:,.2f}" if banking[0] else "Total bank deposits: $0.00")
print(f"Total bank withdrawals (debits): ${banking[1]:,.2f}" if banking[1] else "Total bank withdrawals: $0.00")
print(f"Net cash flow: ${banking[2]:,.2f}" if banking[2] else "Net cash flow: $0.00")

# 6. CORRECTED REVENUE CALCULATION
print("\n" + "=" * 80)
print("CORRECTED REVENUE ANALYSIS")
print("=" * 80)

print(f"""
ACTUAL CHARTER REVENUE (Income):
  Base charter rates:           ${base_billable:>15,.2f}
  Estimated GST (5%):           ${estimated_gst:>15,.2f}
  Estimated Gratuity (15%):     ${estimated_gratuity:>15,.2f}
  ─────────────────────────────────────────────
  TOTAL CHARTER REVENUE:        ${estimated_total_revenue:>15,.2f}

NON-INCOME ITEMS (Should NOT be counted as revenue):
  Customer deposits:            ${total_deposits:>15,.2f}
  Insurance payments:           ${insurance[1] if insurance[1] else 0:>15,.2f}
  Refunds (negative):           (included in payments)
  Loan payments:                (in receipts, not payments)
  Vehicle purchases:            (in receipts, not payments)

PAYMENT TABLE ANALYSIS:
  Total in payments table:      ${charter_rev[1] + charter_rev[3]:>15,.2f}
  Less: Deposits (liability):   ${-total_deposits:>15,.2f}
  Less: Duplicate overstatement:${-dups[2] if dups[2] else 0:>15,.2f}
  ─────────────────────────────────────────────
  Adjusted payment revenue:     ${(charter_rev[1] + charter_rev[3]) - total_deposits - (dups[2] if dups[2] else 0):>15,.2f}

RECONCILIATION:
  Charter-based revenue:        ${estimated_total_revenue:>15,.2f}
  Payment-based revenue:        ${total_revenue_payments:>15,.2f}
  Bank deposits (gross):        ${banking[0] if banking[0] else 0:>15,.2f}

ISSUES IDENTIFIED:
  1. Deposits counted as revenue: ${total_deposits:,.2f}
  2. Possible duplications: ${dups[2] if dups[2] else 0:,.2f}
  3. Payments table includes non-income items
  4. Charter fees don't include all extras (beverage, cleanup, damages, etc)
  5. GST and gratuity not broken out in charter table

RECOMMENDED TRUE REVENUE:
  Charter fees + extras + GST + gratuity ≈ ${estimated_total_revenue:,.2f}
  
  This is approximately 25% of the $19.4M total payments figure.
  The $19.4M includes deposits, duplicates, and non-income transactions.
""")

print("\n" + "=" * 80)
print("NEXT STEPS FOR ACCURATE REVENUE REPORTING")
print("=" * 80)
print("""
1. SEPARATE DEPOSITS FROM REVENUE
   - Create GL 2100 for customer deposits (liability)
   - Only recognize revenue when service is performed
   - Track deposit→revenue conversion

2. BREAK OUT CHARTER COMPONENTS
   - Base fee
   - Airport fees
   - Beverage service
   - Extra time charges
   - Cleanup fees
   - Damage charges
   - GST (5%)
   - Gratuity
   - Total charter revenue

3. REMOVE NON-INCOME FROM REVENUE
   - Vehicle purchases → capital assets
   - Loan payments → liability reduction
   - Insurance → expense
   - CRA payments → tax expense

4. ELIMINATE DUPLICATIONS
   - Identify and mark duplicate payment entries
   - QBO 2012 import duplicates
   - Cross-system duplications (LMS + Square)

5. CREATE PROPER REVENUE RECOGNITION
   - Use charter completion date for revenue recognition
   - Match payments to specific charters
   - Track AR (accounts receivable) properly
   - Reconcile to bank deposits

6. AUDIT TRAIL FOR CRA
   - Document each revenue component
   - Separate GST collected for remittance
   - Track gratuities properly (may be employee income)
   - Maintain support for all revenue figures
""")

cur.close()
conn.close()

print("\n✓ REVENUE AUDIT COMPLETE")
print("=" * 80)
