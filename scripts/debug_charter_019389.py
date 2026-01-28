#!/usr/bin/env python
"""Debug charter 019389 - cancelled but has $500 payment matched."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

rn = '019389'

print('='*80)
print(f'CHARTER {rn} DEBUG')
print('='*80)

# Charter details
cur.execute("""
    SELECT reserve_number, charter_date, account_number, status, cancelled, 
           total_amount_due, paid_amount, balance, notes, booking_notes
    FROM charters WHERE reserve_number=%s
""", (rn,))
charter = cur.fetchone()
print('\nCHARTER DETAILS:')
if charter:
    print(f'  Reserve: {charter[0]}')
    print(f'  Date: {charter[1]}')
    print(f'  Account: {charter[2]}')
    print(f'  Status: {charter[3]}')
    print(f'  Cancelled: {charter[4]}')
    print(f'  Total Due: {charter[5]}')
    print(f'  Paid Amount: {charter[6]}')
    print(f'  Balance: {charter[7]}')
    print(f'  Notes: {charter[8]}')
    print(f'  Booking Notes: {charter[9]}')
else:
    print('  NOT FOUND')

# Charges
cur.execute("""
    SELECT charge_id, description, amount, created_at
    FROM charter_charges WHERE reserve_number=%s
    ORDER BY charge_id
""", (rn,))
charges = cur.fetchall()
print(f'\nCHARGES ({len(charges)}):')
for c in charges:
    print(f'  ID={c[0]} desc="{c[1]}" amount={c[2]} created={c[3]}')
if charges:
    print(f'  TOTAL CHARGES: ${sum(c[2] for c in charges)}')

# Payments linked via payments.reserve_number
cur.execute("""
    SELECT payment_id, reserve_number, amount, payment_date, payment_method, 
           status, notes
    FROM payments 
    WHERE reserve_number=%s
    ORDER BY payment_date
""", (rn,))
payments = cur.fetchall()
print(f'\nPAYMENTS (via payments.reserve_number) ({len(payments)}):')
for p in payments:
    print(f'  ID={p[0]} reserve={p[1]} amount={p[2]} date={p[3]} method={p[4]} status={p[5]} notes={p[6]}')
if payments:
    print(f'  TOTAL PAYMENTS: ${sum((p[2] or 0) for p in payments)}')

# Charter_payments linkages
cur.execute("""
    SELECT cp.id, cp.charter_id, cp.payment_id, cp.amount, 
           p.payment_date, p.payment_method, p.amount as payment_amount
    FROM charter_payments cp
    LEFT JOIN payments p ON p.payment_id = cp.payment_id
    WHERE cp.charter_id=%s
    ORDER BY cp.id
""", (rn,))
cp_links = cur.fetchall()
print(f'\nCHARTER_PAYMENTS LINKS ({len(cp_links)}):')
for cp in cp_links:
    print(f'  CP_ID={cp[0]} charter={cp[1]} payment_id={cp[2]} cp_amount={cp[3]}')
    print(f'    payment_date={cp[4]} method={cp[5]} payment_amount={cp[6]}')
if cp_links:
    print(f'  TOTAL CP AMOUNTS: ${sum((cp[3] or 0) for cp in cp_links)}')

cur.close()
conn.close()
print('\nDone.')
