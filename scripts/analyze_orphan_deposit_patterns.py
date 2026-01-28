#!/usr/bin/env python3
"""
Analyze orphan payments to identify which are likely non-refundable deposits/retainers.
Look for: small amounts, round numbers, deposit keywords, booking patterns.
"""
import psycopg2
from collections import Counter

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print('='*80)
print('ORPHAN PAYMENTS ANALYSIS - NON-REFUNDABLE DEPOSIT IDENTIFICATION')
print('='*80)

# Get all orphan payments
cur.execute("""
    SELECT 
        payment_id, payment_date, amount, payment_method,
        square_payment_id, square_customer_name, 
        COALESCE(notes, '') as notes, 
        COALESCE(status, '') as status,
        COALESCE(square_notes, '') as square_notes
    FROM payments
    WHERE (reserve_number IS NULL OR reserve_number = '')
    AND charter_id IS NULL
    AND COALESCE(status, '') NOT ILIKE '%refund%'
    AND COALESCE(status, '') NOT ILIKE '%void%'
    ORDER BY amount
""")

orphans = cur.fetchall()
total_orphans = len(orphans)
total_amount = sum(float(row[2]) for row in orphans)

print(f'\nTotal orphan payments: {total_orphans} | ${total_amount:,.2f}')

# Analyze amounts
amounts = [float(row[2]) for row in orphans]
amount_counts = Counter(amounts)

print(f'\nAmount statistics:')
print(f'  Min: ${min(amounts):,.2f}')
print(f'  Max: ${max(amounts):,.2f}')
print(f'  Average: ${sum(amounts)/len(amounts):,.2f}')

# Common deposit amounts
common_deposits = [500.00, 250.00, 100.00, 300.00, 200.00, 150.00, 50.00, 75.00]
print(f'\nCommon deposit amounts:')
deposit_count = 0
deposit_total = 0
for amt in common_deposits:
    count = amount_counts.get(amt, 0)
    if count > 0:
        print(f'  ${amt:,.2f}: {count} payment(s) = ${amt * count:,.2f}')
        deposit_count += count
        deposit_total += amt * count

# Round numbers analysis (divisible by 50, under $1000)
round_payments = []
for pid, pdate, amt, method, sq_id, sq_name, notes, status, sq_notes in orphans:
    amt_f = float(amt)
    if amt_f % 50 == 0 and amt_f <= 1000:
        round_payments.append((pid, pdate, amt_f, sq_name))

print(f'\nRound numbers ≤ $1,000 (likely deposits): {len(round_payments)} payments')
if round_payments:
    round_total = sum(p[2] for p in round_payments)
    print(f'  Total: ${round_total:,.2f}')
    unique_amounts = sorted(set(p[2] for p in round_payments))
    print(f'  Amounts: {[f"${a:,.0f}" for a in unique_amounts]}')

# Check for deposit keywords
deposit_keywords = ['deposit', 'retainer', 'non-refundable', 'advance', 'booking', 'hold']
keyword_payments = []
print(f'\nPayments with deposit-related keywords:')
for pid, pdate, amt, method, sq_id, sq_name, notes, status, sq_notes in orphans:
    all_text = f'{notes} {sq_notes}'.lower()
    if any(kw in all_text for kw in deposit_keywords):
        keyword_payments.append((pid, pdate, float(amt), sq_name, all_text[:80]))
        print(f'  Payment {pid} | {pdate} | ${amt:,.2f} | {all_text[:60]}')

if not keyword_payments:
    print('  (None found with explicit deposit keywords)')

# Small payments (≤ $600 - typical deposit range)
small_payments = []
for pid, pdate, amt, method, sq_id, sq_name, notes, status, sq_notes in orphans:
    amt_f = float(amt)
    if amt_f <= 600:
        small_payments.append((pid, pdate, amt_f, sq_name))

print(f'\nSmall payments ≤ $600 (potential deposits): {len(small_payments)}')
if small_payments:
    small_total = sum(p[2] for p in small_payments)
    print(f'  Total: ${small_total:,.2f}')
    print(f'\n  Sample deposits (first 15):')
    for pid, pdate, amt, name in small_payments[:15]:
        print(f'    Payment {pid} | {pdate} | ${amt:,.2f} | {name or "Unknown"}')

# Identify likely deposits (round numbers OR small amounts)
likely_deposits = set()
for pid, pdate, amt, method, sq_id, sq_name, notes, status, sq_notes in orphans:
    amt_f = float(amt)
    # Deposit criteria: round number ≤ $1000 OR ≤ $600
    if (amt_f % 50 == 0 and amt_f <= 1000) or amt_f <= 600:
        likely_deposits.add((pid, pdate, amt_f, sq_name or "Unknown"))

# Summary
print(f'\n' + '='*80)
print('SUMMARY - LIKELY NON-REFUNDABLE DEPOSITS')
print('='*80)
print(f'Total orphan payments: {total_orphans} | ${total_amount:,.2f}')
print(f'')
print(f'Likely deposits (round numbers ≤$1000 OR amounts ≤$600):')
print(f'  Count: {len(likely_deposits)} payments')
likely_total = sum(p[2] for p in likely_deposits)
print(f'  Amount: ${likely_total:,.2f} ({likely_total/total_amount*100:.1f}% of total)')
print(f'')
print(f'Likely full payments (>$600 and not round):')
full_payment_count = total_orphans - len(likely_deposits)
full_payment_total = total_amount - likely_total
print(f'  Count: {full_payment_count} payments')
print(f'  Amount: ${full_payment_total:,.2f} ({full_payment_total/total_amount*100:.1f}% of total)')
print(f'')
print('RECOMMENDATION:')
print(f'  - {len(likely_deposits)} payments (${likely_total:,.2f}) appear to be deposits')
print(f'    → Need charter records created or linked')
print(f'  - {full_payment_count} payments (${full_payment_total:,.2f}) appear to be full payments')
print(f'    → High priority for charter creation')

cur.close()
conn.close()
