#!/usr/bin/env python3
"""
Compare driver names (payees) to e-transfer recipients OUT
and client e-transfer names IN to validate payment flows.
"""

import psycopg2
import os
from difflib import SequenceMatcher

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("\n" + "="*80)
print("E-TRANSFER VALIDATION: DRIVERS vs CLIENTS")
print("="*80)

# 1. Get driver names from employees
cur.execute("""
    SELECT DISTINCT full_name 
    FROM employees 
    WHERE full_name IS NOT NULL
    ORDER BY full_name
""")
drivers = [r[0] for r in cur.fetchall()]
print(f"\n1. Known drivers/employees: {len(drivers)}")

# 2. Get e-transfer OUT recipients from banking (debits with E-TRANSFER)
cur.execute("""
    SELECT DISTINCT 
        REGEXP_REPLACE(description, '^E-?TRANSFER.*?TO\\s+', '', 'i') as recipient,
        COUNT(*) as count,
        SUM(debit_amount) as total
    FROM banking_transactions
    WHERE debit_amount > 0
    AND description ILIKE '%e-transfer%'
    OR description ILIKE '%etransfer%'
    GROUP BY recipient
    ORDER BY total DESC
""")
etransfer_out = cur.fetchall()
print(f"\n2. E-transfer OUT recipients: {len(etransfer_out)}")
print(f"\n   {'Recipient':40} {'Count':>6} {'Total':>12}")
print(f"   {'-'*60}")
for recip, count, total in etransfer_out[:20]:
    print(f"   {recip[:40]:40} {count:6} ${total:>10,.2f}")

# 3. Get e-transfer IN senders from banking (credits with E-TRANSFER)
cur.execute("""
    SELECT DISTINCT
        REGEXP_REPLACE(description, '^E-?TRANSFER.*?FROM\\s+', '', 'i') as sender,
        COUNT(*) as count,
        SUM(credit_amount) as total
    FROM banking_transactions
    WHERE credit_amount > 0
    AND (description ILIKE '%e-transfer%' OR description ILIKE '%etransfer%')
    GROUP BY sender
    ORDER BY total DESC
""")
etransfer_in = cur.fetchall()
print(f"\n3. E-transfer IN senders: {len(etransfer_in)}")
print(f"\n   {'Sender':40} {'Count':>6} {'Total':>12}")
print(f"   {'-'*60}")
for sender, count, total in etransfer_in[:20]:
    print(f"   {sender[:40]:40} {count:6} ${total:>10,.2f}")

# 4. Match e-transfer OUT to known drivers (fuzzy)
print(f"\n4. E-transfer OUT → Driver Matches (>70% similarity):")
print(f"   {'-'*80}")

def fuzzy_match(name1, name2):
    return SequenceMatcher(None, name1.lower(), name2.lower()).ratio()

matched_out = []
for recip, count, total in etransfer_out:
    for driver in drivers:
        ratio = fuzzy_match(recip, driver)
        if ratio > 0.7:
            matched_out.append((recip, driver, ratio, count, total))
            print(f"   {recip[:30]:30} → {driver[:30]:30} ({ratio:.0%}) ${total:>10,.2f}")

# 5. Match e-transfer IN to clients
cur.execute("""
    SELECT DISTINCT client_name 
    FROM clients 
    WHERE client_name IS NOT NULL
    ORDER BY client_name
""")
clients = [r[0] for r in cur.fetchall()]

print(f"\n5. E-transfer IN → Client Matches (>70% similarity):")
print(f"   {'-'*80}")

matched_in = []
for sender, count, total in etransfer_in:
    for client in clients:
        ratio = fuzzy_match(sender, client)
        if ratio > 0.7:
            matched_in.append((sender, client, ratio, count, total))
            print(f"   {sender[:30]:30} → {client[:30]:30} ({ratio:.0%}) ${total:>10,.2f}")
            break

# 6. Unmatched e-transfers OUT
print(f"\n6. UNMATCHED E-transfer OUT (not driver payments):")
print(f"   {'-'*80}")
matched_recips = {m[0] for m in matched_out}
for recip, count, total in etransfer_out:
    if recip not in matched_recips:
        print(f"   {recip[:50]:50} {count:3} txns ${total:>10,.2f}")

# 7. Unmatched e-transfers IN
print(f"\n7. UNMATCHED E-transfer IN (not from clients):")
print(f"   {'-'*80}")
matched_senders = {m[0] for m in matched_in}
for sender, count, total in etransfer_in:
    if sender not in matched_senders:
        print(f"   {sender[:50]:50} {count:3} txns ${total:>10,.2f}")

# Summary
print(f"\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"\nE-transfers OUT:")
print(f"  Total recipients: {len(etransfer_out)}")
print(f"  Matched to drivers: {len(matched_out)}")
print(f"  Unmatched: {len(etransfer_out) - len(matched_out)}")

print(f"\nE-transfers IN:")
print(f"  Total senders: {len(etransfer_in)}")
print(f"  Matched to clients: {len(matched_in)}")
print(f"  Unmatched: {len(etransfer_in) - len(matched_in)}")

cur.close()
conn.close()
