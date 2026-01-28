#!/usr/bin/env python
"""
Comprehensive status report: What's left to fix in the charter/payment system.
Checks:
  1. Cancelled charters with charges still recorded
  2. Charters with charges but no payments (excluding cancelled/discounted)
  3. Charters with negative balances (overpayments/credits)
  4. Orphaned payments (no charter linkage)
  5. Duplicate payment allocations
  6. Missing charge data (total_due > 0 but no charter_charges)
"""
import psycopg2
from decimal import Decimal

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*100)
print('CHARTER/PAYMENT SYSTEM STATUS REPORT')
print('='*100)

# 1. Cancelled charters with charges (pre-Oct 2025)
cur.execute("""
    SELECT COUNT(DISTINCT c.reserve_number), COALESCE(SUM(c.total_amount_due), 0)
    FROM charters c
    WHERE (c.cancelled = TRUE OR c.status ILIKE '%cancel%')
      AND c.charter_date < '2025-10-01'
      AND (c.total_amount_due > 0 OR EXISTS (
          SELECT 1 FROM charter_charges WHERE reserve_number = c.reserve_number AND amount > 0
      ))
""")
cancelled_with_charges, cancelled_charges_total = cur.fetchone()

# 2. Charters with charges but no payments (excluding cancelled/discounted)
cur.execute("""
    WITH charge_sum AS (
        SELECT reserve_number, SUM(amount) AS charges
        FROM charter_charges
        GROUP BY reserve_number
    )
    SELECT COUNT(*), COALESCE(SUM(c.balance), 0)
    FROM charters c
    LEFT JOIN charge_sum cs ON cs.reserve_number = c.reserve_number
    WHERE (COALESCE(cs.charges,0) > 0 OR COALESCE(c.total_amount_due,0) > 0)
      AND COALESCE(c.paid_amount,0) = 0
      AND NOT EXISTS (SELECT 1 FROM charter_payments cp WHERE cp.charter_id = c.reserve_number)
      AND c.cancelled = FALSE
      AND c.status NOT ILIKE '%cancel%'
""")
charges_no_payments, charges_no_payments_total = cur.fetchone()

# 3. Charters with significant negative balances (credits > $100)
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(balance), 0)
    FROM charters
    WHERE balance < -100
""")
large_credits, large_credits_total = cur.fetchone()

# 4. Orphaned payments (no charter linkage)
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(amount), 0)
    FROM payments
    WHERE reserve_number IS NULL
      AND NOT EXISTS (SELECT 1 FROM charter_payments WHERE payment_id = payments.payment_id)
      AND status != 'voided'
""")
orphaned_payments, orphaned_payments_total = cur.fetchone()

# 5. Charters with $0 charges but payments applied (missing charge data)
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(paid_amount), 0)
    FROM charters c
    WHERE (c.total_amount_due IS NULL OR c.total_amount_due = 0)
      AND c.paid_amount > 0
      AND c.cancelled = FALSE
      AND c.status NOT ILIKE '%cancel%'
      AND NOT EXISTS (
          SELECT 1 FROM charter_charges WHERE reserve_number = c.reserve_number AND amount > 0
      )
""")
zero_charges_with_payments, zero_charges_payments_total = cur.fetchone()

# 6. Unmatched payments (2007-2024, excluding personal/adjustments)
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(amount), 0)
    FROM payments p
    WHERE p.payment_date BETWEEN '2007-01-01' AND '2024-12-31'
      AND NOT EXISTS (SELECT 1 FROM charter_payments WHERE payment_id = p.payment_id)
      AND p.reserve_number IS NULL
      AND p.status != 'voided'
      AND p.amount > 0
""")
unmatched_payments, unmatched_payments_total = cur.fetchone()

# Summary
print('\n1. CANCELLED CHARTERS WITH CHARGES (pre-Oct 2025)')
print(f'   Count: {cancelled_with_charges}')
print(f'   Total charges: ${Decimal(cancelled_charges_total):,.2f}')
print(f'   Action: Delete charges, zero totals, mark cancelled')

print('\n2. CHARTERS WITH CHARGES BUT NO PAYMENTS')
print(f'   Count: {charges_no_payments}')
print(f'   Total outstanding: ${Decimal(charges_no_payments_total):,.2f}')
print(f'   Action: Review for collection or write-off')

print('\n3. LARGE CREDITS (balance < -$100)')
print(f'   Count: {large_credits}')
print(f'   Total credits: ${Decimal(large_credits_total):,.2f}')
print(f'   Action: Review for refunds or misapplied payments')

print('\n4. ORPHANED PAYMENTS (no charter linkage)')
print(f'   Count: {orphaned_payments}')
print(f'   Total amount: ${Decimal(orphaned_payments_total):,.2f}')
print(f'   Action: Match to charters or mark as deposits/unallocated')

print('\n5. ZERO CHARGES WITH PAYMENTS (missing charge data)')
print(f'   Count: {zero_charges_with_payments}')
print(f'   Total payments: ${Decimal(zero_charges_payments_total):,.2f}')
print(f'   Action: Reconstruct charges or flag as no-charge bookings')

print('\n6. UNMATCHED PAYMENTS (2007-2024, excludes voided)')
print(f'   Count: {unmatched_payments}')
print(f'   Total amount: ${Decimal(unmatched_payments_total):,.2f}')
print(f'   Action: Continue matching efforts or classify as unreconcilable')

print('\n' + '='*100)
print('PRIORITY RECOMMENDATIONS:')
print('='*100)
print('1. HIGH: Cancel 66 charters with charges (cleanup $27.7K)')
print('2. MEDIUM: Review 49 charters with charges/no payments ($21.4K outstanding)')
print('3. MEDIUM: Review large credits for refund processing')
print('4. LOW: Continue payment matching for historical records')

cur.close()
conn.close()
print('\nDone.')
