#!/usr/bin/env python
"""
Search for $500 payments that might match the orphaned paid_amount entries.
Look for payments with amount=$500 that have either:
  - No charter_payments linkage
  - charter_payments pointing to charters with orphaned paid_amount
"""
import psycopg2
from collections import defaultdict

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*100)
print('Searching for $500 payments and their linkages')
print('='*100)

# Get all $500 payments
cur.execute("""
    SELECT payment_id, reserve_number, account_number, amount, payment_date, 
           payment_method, status, notes
    FROM payments
    WHERE ABS(amount - 500.00) < 0.01
    ORDER BY payment_date DESC
    LIMIT 100
""")
payments_500 = cur.fetchall()

print(f'\nFound {len(payments_500)} payments with amount ≈ $500 (showing first 100)')

# For each, check charter_payments linkage
linked_count = 0
unlinked_count = 0
orphan_linked_count = 0

for p in payments_500[:20]:  # Check first 20
    payment_id, reserve_number, account_number, amount, payment_date, payment_method, status, notes = p
    
    # Check charter_payments
    cur.execute("SELECT charter_id, amount FROM charter_payments WHERE payment_id=%s", (payment_id,))
    cp_links = cur.fetchall()
    
    print(f'\nPayment {payment_id}: reserve={reserve_number} acct={account_number} date={payment_date} ${amount}')
    print(f'  Method: {payment_method} Status: {status}')
    
    if cp_links:
        print(f'  Charter_payments links: {len(cp_links)}')
        for charter_id, cp_amount in cp_links:
            # Check if this charter has orphaned paid_amount
            cur.execute("""
                SELECT paid_amount, balance, 
                       (SELECT COUNT(*) FROM charter_payments WHERE charter_id = %s) as cp_count,
                       (SELECT COUNT(*) FROM payments WHERE reserve_number = %s) as p_count
                FROM charters WHERE reserve_number = %s
            """, (charter_id, charter_id, charter_id))
            charter_info = cur.fetchone()
            if charter_info:
                paid_amount, balance, cp_count, p_count = charter_info
                print(f'    → Charter {charter_id}: paid=${paid_amount} balance={balance} cp_count={cp_count} p_count={p_count}')
                if cp_count == 1 and p_count == 0:
                    orphan_linked_count += 1
                    print(f'      *** ORPHAN PATTERN: charter_payments exists but no payments.reserve_number')
        linked_count += 1
    else:
        print(f'  NO charter_payments links')
        if reserve_number:
            # Check if reserve_number exists in charters
            cur.execute("SELECT paid_amount, balance FROM charters WHERE reserve_number=%s", (reserve_number,))
            charter = cur.fetchone()
            if charter:
                print(f'    Reserve {reserve_number} exists: paid=${charter[0]} balance={charter[1]}')
        unlinked_count += 1

print(f'\n=== SUMMARY (first 20 payments) ===')
print(f'Linked via charter_payments: {linked_count}')
print(f'Unlinked (no charter_payments): {unlinked_count}')
print(f'Orphan pattern (cp exists, p.reserve_number missing): {orphan_linked_count}')

cur.close()
conn.close()
print('\nDone.')
