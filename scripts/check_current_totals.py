#!/usr/bin/env python
"""
Check current system totals before removing 2025-07-24 duplicates.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*100)
print('CURRENT SYSTEM TOTALS')
print('='*100)

# Overall charter statistics
cur.execute("""
    SELECT 
        COUNT(*) as total_charters,
        COUNT(CASE WHEN total_amount_due > 0 THEN 1 END) as with_charges,
        SUM(total_amount_due) as total_due,
        SUM(paid_amount) as total_paid,
        SUM(balance) as total_balance
    FROM charters
""")
charter_stats = cur.fetchone()

print(f'\nCharter Statistics:')
print(f'  Total charters: {charter_stats[0]:,}')
print(f'  Charters with charges: {charter_stats[1]:,}')
print(f'  Total amount due: ${charter_stats[2] or 0:,.2f}')
print(f'  Total paid: ${charter_stats[3] or 0:,.2f}')
print(f'  Total balance: ${charter_stats[4] or 0:,.2f}')

# Credits breakdown
cur.execute("""
    SELECT 
        COUNT(*) as credit_count,
        SUM(balance) as credit_total,
        MIN(balance) as largest_credit,
        AVG(balance) as avg_credit
    FROM charters
    WHERE balance < 0
""")
credit_stats = cur.fetchone()

print(f'\nCredits (Overpayments):')
print(f'  Charters with credits: {credit_stats[0]:,}')
print(f'  Total credits: ${credit_stats[1] or 0:,.2f}')
print(f'  Largest credit: ${credit_stats[2] or 0:,.2f}')
print(f'  Average credit: ${credit_stats[3] or 0:,.2f}')

# Urgent credits
cur.execute("""
    SELECT COUNT(*), SUM(balance)
    FROM charters
    WHERE balance < -2000
""")
urgent_stats = cur.fetchone()

print(f'\nUrgent Credits (< -$2K):')
print(f'  Count: {urgent_stats[0]}')
print(f'  Total: ${urgent_stats[1] or 0:,.2f}')

# Outstanding balances
cur.execute("""
    SELECT 
        COUNT(*) as outstanding_count,
        SUM(balance) as outstanding_total,
        MAX(balance) as largest_outstanding
    FROM charters
    WHERE balance > 0
""")
outstanding_stats = cur.fetchone()

print(f'\nOutstanding Balances (Unpaid):')
print(f'  Charters with balance due: {outstanding_stats[0]:,}')
print(f'  Total outstanding: ${outstanding_stats[1] or 0:,.2f}')
print(f'  Largest outstanding: ${outstanding_stats[2] or 0:,.2f}')

# Payment statistics
cur.execute("""
    SELECT 
        COUNT(*) as payment_count,
        SUM(amount) as payment_total,
        COUNT(DISTINCT reserve_number) as charters_with_payments
    FROM payments
    WHERE reserve_number IS NOT NULL
""")
payment_stats = cur.fetchone()

print(f'\nPayment Statistics:')
print(f'  Total payment records: {payment_stats[0]:,}')
print(f'  Total payment amount: ${payment_stats[1] or 0:,.2f}')
print(f'  Charters with payments: {payment_stats[2]:,}')

# 2025-07-24 batch impact
cur.execute("""
    SELECT COUNT(*), SUM(amount)
    FROM payments
    WHERE payment_date = '2025-07-24'
""")
batch_stats = cur.fetchone()

print(f'\n2025-07-24 Batch:')
print(f'  Payments: {batch_stats[0]}')
print(f'  Total amount: ${batch_stats[1] or 0:,.2f}')

# Potential impact of removing duplicates
cur.execute("""
    WITH jul24_payments AS (
        SELECT payment_id, reserve_number, amount
        FROM payments
        WHERE payment_date = '2025-07-24'
          AND reserve_number IS NOT NULL
    ),
    earlier_payments AS (
        SELECT reserve_number, amount
        FROM payments
        WHERE payment_date < '2025-07-24'
          AND reserve_number IS NOT NULL
    )
    SELECT COUNT(*), SUM(j.amount)
    FROM jul24_payments j
    INNER JOIN earlier_payments e ON e.reserve_number = j.reserve_number
                                 AND e.amount = j.amount
""")
dupe_stats = cur.fetchone()

print(f'\nDuplicate Analysis:')
print(f'  Duplicate payments identified: {dupe_stats[0]}')
print(f'  Duplicate amount: ${dupe_stats[1] or 0:,.2f}')
print(f'  After removal:')
print(f'    Total paid would be: ${(payment_stats[1] or 0) - (dupe_stats[1] or 0):,.2f}')
print(f'    Total balance would be: ${(charter_stats[4] or 0) + (dupe_stats[1] or 0):,.2f}')
print(f'    Credits would be: ${(credit_stats[1] or 0) + (dupe_stats[1] or 0):,.2f}')

cur.close()
conn.close()
print('\nDone.')
