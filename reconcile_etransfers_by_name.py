#!/usr/bin/env python3
"""Reconcile e-transfers to charters by client name matching."""
import psycopg2
import os
from datetime import datetime, timedelta
import re

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Get unmatched customer e-transfers (exclude employee names)
employee_names = [
    'BARB PEACOCK', 'BARBARA PEACOCK',
    'DAVID RICHARD', 'PAUL RICHARD', 'MATTHEW RICHARD',
    'JERRY SCHANDRIP', 'JEANNIE SHILLINGTON', 'MICHAEL RICHARD'
]

print("\n" + "=" * 120)
print("E-TRANSFER TO CHARTER RECONCILIATION - CLIENT NAME MATCHING".center(120))
print("=" * 120)

# Get all customer e-transfers (not matched to payments yet)
cur.execute('''
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.credit_amount,
        bt.description,
        bt.reconciled_payment_id
    FROM banking_transactions bt
    WHERE bt.credit_amount > 0
      AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%')
      AND bt.reconciled_payment_id IS NULL
      AND bt.description NOT ILIKE '%BARB%'
      AND bt.description NOT ILIKE '%DAVID RICHARD%'
      AND bt.description NOT ILIKE '%PAUL RICHARD%'
      AND bt.description NOT ILIKE '%MATTHEW RICHARD%'
      AND bt.description NOT ILIKE '%JERRY%'
      AND bt.description NOT ILIKE '%JEANNIE%'
      AND bt.description NOT ILIKE '%MICHAEL RICHARD%'
    ORDER BY bt.transaction_date DESC;
''')

etransfers = cur.fetchall()
print(f"\n📊 Found {len(etransfers)} unmatched customer e-transfers")
print(f"   Total: ${sum(e[2] for e in etransfers):,.2f}\n")

# Extract client names from e-transfer descriptions
def extract_name_from_etransfer(description):
    """Extract client name from e-transfer description."""
    desc_upper = description.upper()
    
    # Common patterns:
    # "E-TRANSFER FROM JOHN SMITH"
    # "ETRANSFER JOHN SMITH"
    # "E-TRANSFER - JOHN SMITH"
    
    # Remove common prefixes
    for prefix in ['E-TRANSFER FROM', 'ETRANSFER FROM', 'E-TRANSFER -', 'ETRANSFER -', 'E-TRANSFER', 'ETRANSFER']:
        if prefix in desc_upper:
            desc_upper = desc_upper.replace(prefix, '').strip()
            break
    
    # Remove dates, amounts, reference numbers
    desc_upper = re.sub(r'\d{4}-\d{2}-\d{2}', '', desc_upper)
    desc_upper = re.sub(r'\$[\d,\.]+', '', desc_upper)
    desc_upper = re.sub(r'REF#?\s*\d+', '', desc_upper)
    desc_upper = re.sub(r'CONF#?\s*\d+', '', desc_upper)
    
    # Clean up
    desc_upper = desc_upper.strip()
    
    return desc_upper if desc_upper else None

# Get all clients
cur.execute('''
    SELECT DISTINCT
        cl.client_id,
        cl.client_name,
        UPPER(cl.client_name) as name_upper
    FROM clients cl
    WHERE cl.client_name IS NOT NULL
    ORDER BY cl.client_name;
''')

clients = cur.fetchall()
client_lookup = {c[2]: c for c in clients}  # Upper name -> (client_id, original_name, upper_name)

print("=" * 120)
print("MATCHING E-TRANSFERS TO CLIENTS:")
print("=" * 120)

matched_exact = []
matched_partial = []
unmatched = []

for etransfer in etransfers:
    trans_id, trans_date, amount, description, _ = etransfer
    
    name_from_etransfer = extract_name_from_etransfer(description)
    
    if not name_from_etransfer:
        unmatched.append((etransfer, None, 'NO_NAME_EXTRACTED'))
        continue
    
    # Try exact match
    if name_from_etransfer in client_lookup:
        client = client_lookup[name_from_etransfer]
        matched_exact.append((etransfer, client, 'EXACT'))
        continue
    
    # Try partial match (contains)
    found_partial = None
    for client_name_upper, client in client_lookup.items():
        if name_from_etransfer in client_name_upper or client_name_upper in name_from_etransfer:
            if len(name_from_etransfer) >= 5:  # Minimum 5 chars for partial match
                found_partial = client
                break
    
    if found_partial:
        matched_partial.append((etransfer, found_partial, 'PARTIAL'))
    else:
        unmatched.append((etransfer, name_from_etransfer, 'NO_CLIENT_MATCH'))

print(f"\n📊 MATCHING RESULTS:")
print(f"   Exact Matches:    {len(matched_exact):>4} e-transfers | ${sum(e[0][2] for e in matched_exact):>12,.2f}")
print(f"   Partial Matches:  {len(matched_partial):>4} e-transfers | ${sum(e[0][2] for e in matched_partial):>12,.2f}")
print(f"   Unmatched:        {len(unmatched):>4} e-transfers | ${sum(e[0][2] for e in unmatched):>12,.2f}")

# For matched clients, find their charters within date range
print("\n" + "=" * 120)
print("FINDING CHARTERS FOR MATCHED CLIENTS:")
print("=" * 120)

payment_candidates = []

for etransfer, client, match_type in (matched_exact + matched_partial):
    trans_id, trans_date, amount, description, _ = etransfer
    client_id, client_name, _ = client
    
    # Find charters for this client within ±365 days
    date_from = trans_date - timedelta(days=365)
    date_to = trans_date + timedelta(days=365)
    
    cur.execute('''
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.total_amount_due,
            c.paid_amount,
            (c.total_amount_due - c.paid_amount) as balance,
            c.status
        FROM charters c
        WHERE c.client_id = %s
          AND c.charter_date BETWEEN %s AND %s
          AND c.total_amount_due > 0
        ORDER BY ABS(c.total_amount_due - c.paid_amount - %s) ASC
        LIMIT 5;
    ''', (client_id, date_from, date_to, amount))
    
    charters = cur.fetchall()
    
    if charters:
        payment_candidates.append({
            'etransfer': etransfer,
            'client': client,
            'match_type': match_type,
            'charters': charters
        })

print(f"\n✅ Found {len(payment_candidates)} e-transfers with matching charters")

# Show sample matches (first 20)
print("\n" + "=" * 120)
print("SAMPLE E-TRANSFER → CHARTER MATCHES (showing first 20):")
print("=" * 120)
print(f"{'Date':<12} | {'Amount':>10} | {'Client':<30} | {'Match':<7} | Charter Matches")
print("-" * 120)

for i, candidate in enumerate(payment_candidates[:20]):
    etransfer = candidate['etransfer']
    client = candidate['client']
    match_type = candidate['match_type']
    charters = candidate['charters']
    
    trans_date = etransfer[1].strftime('%Y-%m-%d')
    amount = etransfer[2]
    client_name = client[1][:29]
    
    # Show best charter match
    if charters:
        charter = charters[0]
        charter_info = f"#{charter[1]} Balance: ${charter[5]:.2f}"
        if len(charters) > 1:
            charter_info += f" (+{len(charters)-1} more)"
    else:
        charter_info = "No matches"
    
    print(f"{trans_date} | ${amount:>9.2f} | {client_name:<30} | {match_type:<7} | {charter_info}")

if len(payment_candidates) > 20:
    print(f"... and {len(payment_candidates) - 20} more matches")

# Show unmatched details
if unmatched:
    print("\n" + "=" * 120)
    print(f"UNMATCHED E-TRANSFERS ({len(unmatched)} total, showing first 20):")
    print("=" * 120)
    print(f"{'Date':<12} | {'Amount':>10} | {'Extracted Name':<40} | Description")
    print("-" * 120)
    
    for i, (etransfer, extracted_name, reason) in enumerate(unmatched[:20]):
        trans_date = etransfer[1].strftime('%Y-%m-%d')
        amount = etransfer[2]
        name = (extracted_name or reason)[:39]
        desc = etransfer[3][:50]
        print(f"{trans_date} | ${amount:>9.2f} | {name:<40} | {desc}")
    
    if len(unmatched) > 20:
        print(f"... and {len(unmatched) - 20} more unmatched")

print("\n" + "=" * 120)
print("💡 NEXT STEPS:")
print("=" * 120)
print(f"\n1. CREATE PAYMENTS for {len(payment_candidates)} matched e-transfers")
print(f"   - Link e-transfer to charter via reserve_number")
print(f"   - Update banking_transactions.reconciled_payment_id")
print(f"   - Handle multi-charter bookings (same client, multiple charters)")
print(f"\n2. MANUAL REVIEW for {len(unmatched)} unmatched e-transfers")
print(f"   - Check if client names need standardization")
print(f"   - Verify if these are refunds, deposits, or other transactions")
print(f"\n3. VERIFY 2026 CHARTERS receive their e-transfer payments")

print("\n" + "=" * 120 + "\n")

cur.close()
conn.close()
