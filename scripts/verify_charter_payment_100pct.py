#!/usr/bin/env python3
"""
Step 3: Verify all 18,722 charters have complete payment matches
Includes: cash, check, Square, NRD, all payment methods
Identifies charters with missing or incomplete payment records
"""

import psycopg2
import os
from collections import defaultdict

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print('\n' + '='*120)
print('STEP 3: VERIFY ALL CHARTERS - 100% PAYMENT MATCHING')
print('='*120 + '\n')

# Step 1: Get all charters
cur.execute('''
    SELECT COUNT(*) FROM charters
''')
total_charters = cur.fetchone()[0]

print(f'Total charters in system: {total_charters:,}')
print()

# Step 2: Get charters with matching payments
cur.execute('''
    SELECT DISTINCT c.charter_id, c.reserve_number, c.total_amount_due
    FROM charters c
    LEFT JOIN payments p ON c.reserve_number = p.reserve_number
    WHERE p.payment_id IS NOT NULL
    ORDER BY c.charter_id
''')
charters_with_payments = {}
for charter_id, reserve_num, amount_due in cur.fetchall():
    charters_with_payments[charter_id] = {
        'reserve_number': reserve_num,
        'amount_due': amount_due
    }

print(f'Charters with at least 1 payment: {len(charters_with_payments):,}')
print()

# Step 3: Get charters with NO payments (critical issue)
cur.execute('''
    SELECT c.charter_id, c.reserve_number, c.total_amount_due, c.charter_date
    FROM charters c
    LEFT JOIN payments p ON c.reserve_number = p.reserve_number
    WHERE p.payment_id IS NULL
    GROUP BY c.charter_id, c.reserve_number, c.total_amount_due, c.charter_date
    ORDER BY c.charter_id
''')
charters_no_payments = {}
for charter_id, reserve_num, amount_due, charter_date in cur.fetchall():
    charters_no_payments[charter_id] = {
        'reserve_number': reserve_num,
        'amount_due': float(amount_due) if amount_due else 0,
        'charter_date': charter_date
    }

print(f'⚠️  Charters with ZERO payments: {len(charters_no_payments):,}')
if len(charters_no_payments) > 0 and len(charters_no_payments) <= 20:
    print('   Sample missing payment charters:')
    for i, (cid, data) in enumerate(list(charters_no_payments.items())[:20]):
        print(f'   - Reserve {data["reserve_number"]}: ${data["amount_due"]:>10,.2f} ({data["charter_date"]})')
print()

# Step 4: Payment method breakdown
print('Payment methods in system:')
cur.execute('''
    SELECT payment_method, COUNT(*) as count, COALESCE(SUM(amount), 0) as total
    FROM payments
    GROUP BY payment_method
    ORDER BY count DESC
''')
for method, count, total in cur.fetchall():
    method_display = 'NULL' if method is None else str(method)
    print(f'  {method_display:20s}: {count:>6,} payments, ${total:>12,.2f}')
print()

# Step 5: Charters with partial vs full payment
cur.execute('''
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.total_amount_due,
        COALESCE(SUM(p.amount), 0) as total_paid,
        COUNT(p.payment_id) as payment_count,
        COUNT(DISTINCT p.payment_method) as payment_method_count
    FROM charters c
    LEFT JOIN payments p ON c.reserve_number = p.reserve_number
    GROUP BY c.charter_id, c.reserve_number, c.total_amount_due
    HAVING c.total_amount_due > 0
    ORDER BY c.charter_id
''')

full_match = 0
partial_match = 0
over_paid = 0
unpaid = 0

for charter_id, reserve_num, amount_due, paid, pc, pmc in cur.fetchall():
    if amount_due is None:
        continue
    
    amount_due = float(amount_due)
    paid = float(paid)
    
    if paid == 0:
        unpaid += 1
    elif abs(paid - amount_due) < 0.01:  # Zero tolerance (to the penny)
        full_match += 1
    elif paid > amount_due:
        over_paid += 1
    else:
        partial_match += 1

print('Charter payment reconciliation:')
print(f'  ✅ Fully matched (paid = due):    {full_match:>6,}')
print(f'  ⚠️  Partially paid (0 < paid < due): {partial_match:>6,}')
print(f'  ❌ Over-paid (paid > due):        {over_paid:>6,}')
print(f'  ❌ Unpaid (paid = 0):             {unpaid:>6,}')
print()

# Step 6: Identify charters missing from LMS data
cur.execute('''
    SELECT COUNT(*) FROM charters 
    WHERE reserve_number NOT IN (
        SELECT DISTINCT reserve_number FROM payments WHERE reserve_number IS NOT NULL
    )
    AND total_amount_due > 0
''')
missing_from_payments = cur.fetchone()[0]

print(f'Charters with amount due but NO payment records: {missing_from_payments:,}')
print()

# Step 7: Check NRD payments specifically
print('NRD (Non-Reserve Deposit) Breakdown:')
cur.execute('''
    SELECT 
        COUNT(*) as nrd_count,
        COALESCE(SUM(amount), 0) as total,
        COUNT(DISTINCT reserve_number) as charters_with_nrd
    FROM payments
    WHERE notes LIKE '%NRD%' OR notes LIKE '%non-reserve%'
''')
nrd_count, nrd_total, nrd_charters = cur.fetchone()
print(f'  NRD payments found: {nrd_count:,} (${nrd_total:,.2f})')
print(f'  Charters with NRD: {nrd_charters:,}')
print()

# Step 8: Orphaned payments (no matching charter)
cur.execute('''
    SELECT COUNT(*), COALESCE(SUM(amount), 0)
    FROM payments
    WHERE reserve_number IS NULL
    AND payment_method = 'credit_card'
''')
orphaned_count, orphaned_total = cur.fetchone()

print(f'Orphaned Square payments (no reserve_number): {orphaned_count:,} (${orphaned_total:,.2f})')
print()

# Step 9: Detailed report on payment method distribution by charter
print('='*120)
print('DETAILED ANALYSIS: CHARTERS BY PAYMENT METHOD COVERAGE')
print('='*120 + '\n')

cur.execute('''
    SELECT 
        COUNT(DISTINCT c.charter_id) as charter_count,
        COALESCE(STRING_AGG(DISTINCT p.payment_method, ', '), 'NONE') as methods
    FROM charters c
    LEFT JOIN payments p ON c.reserve_number = p.reserve_number
    WHERE c.total_amount_due > 0
    GROUP BY COALESCE(STRING_AGG(DISTINCT p.payment_method, ', '), 'NONE')
    ORDER BY charter_count DESC
''')

print('Charters by payment method coverage:')
for count, methods in cur.fetchall():
    if methods == 'NONE':
        print(f'  ❌ {count:>6,} charters with NO payments')
    else:
        print(f'  ✅ {count:>6,} charters with payments: {methods}')
print()

# Step 10: Export detailed mismatched charters
print('='*120)
print('CHARTERS WITH PAYMENT ISSUES')
print('='*120 + '\n')

cur.execute('''
    SELECT 
        c.charter_id,
        c.reserve_number,
        ROUND(c.total_amount_due::numeric, 2) as amount_due,
        COUNT(p.payment_id) as payment_count,
        ROUND(COALESCE(SUM(p.amount), 0)::numeric, 2) as total_paid,
        STRING_AGG(DISTINCT p.payment_method, ', ') as payment_methods,
        c.charter_date
    FROM charters c
    LEFT JOIN payments p ON c.reserve_number = p.reserve_number
    WHERE c.total_amount_due > 0
    AND (
        COALESCE(SUM(p.amount), 0) = 0  -- Unpaid
        OR ABS(COALESCE(SUM(p.amount), 0) - c.total_amount_due) > 0.01  -- Mismatch
    )
    GROUP BY c.charter_id, c.reserve_number, c.total_amount_due, c.charter_date
    ORDER BY c.total_amount_due DESC
    LIMIT 50
''')

issues = cur.fetchall()
if issues:
    print(f'Top 50 charters with payment mismatches:\n')
    print(f'{"Reserve":<12} {"Amount Due":>12} {"Paid":>12} {"Status":<20} {"Methods":<30} {"Date":<12}')
    print('-'*120)
    
    for reserve, amount_due, paid, count, paid_sum, methods, charter_date in issues:
        if paid_sum == 0:
            status = '❌ UNPAID'
        elif abs(paid_sum - amount_due) > 0.01:
            diff = amount_due - paid_sum
            status = f'⚠️  SHORT ${diff:,.2f}'
        else:
            status = '✅ MATCHED'
        
        methods_str = (methods or 'NONE')[:28]
        print(f'{reserve:<12} ${amount_due:>10,.2f} ${paid_sum:>10,.2f} {status:<20} {methods_str:<30} {str(charter_date):<12}')

print()

# Step 11: Summary metrics
print('='*120)
print('SUMMARY METRICS')
print('='*120 + '\n')

cur.execute('''
    SELECT 
        COUNT(*) as charters,
        COALESCE(SUM(total_amount_due), 0) as total_due
    FROM charters
    WHERE total_amount_due > 0
''')
total_due_system, total_due_amount = cur.fetchone()

cur.execute('''
    SELECT 
        COUNT(DISTINCT reserve_number) as charters_paid,
        COALESCE(SUM(amount), 0) as total_received
    FROM payments
    WHERE reserve_number IS NOT NULL
''')
charters_paid, total_received = cur.fetchone()

print(f'System Totals:')
print(f'  Charters with due amount: {total_due_system:,}')
print(f'  Total amount due: ${total_due_amount:,.2f}')
print()

print(f'Payment Collection:')
print(f'  Charters with payment(s): {charters_paid:,}')
print(f'  Total received: ${total_received:,.2f}')
print(f'  Collection rate: {(charters_paid / total_due_system * 100):.1f}%')
print()

print(f'Gap Analysis:')
gap_charters = total_due_system - charters_paid
gap_amount = total_due_amount - total_received
print(f'  Charters missing payments: {gap_charters:,}')
print(f'  Uncollected funds: ${gap_amount:,.2f}')
print()

print('='*120)
print('VERIFICATION COMPLETE')
print('='*120 + '\n')

cur.close()
conn.close()
