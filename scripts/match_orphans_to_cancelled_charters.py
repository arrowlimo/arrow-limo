#!/usr/bin/env python3
"""
Match orphan payments to cancelled charters with retainers.
Since Square customer names are missing, we'll match by:
1. Payment amount to cancelled charter retainer amount
2. Payment date proximity to charter cancellation
3. Client negative balance (retainer held in escrow)
"""
import psycopg2
from datetime import timedelta

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print('='*80)
print('MATCHING ORPHAN PAYMENTS TO CANCELLED CHARTERS WITH RETAINERS')
print('='*80)

# Get orphan payments
cur.execute("""
    SELECT payment_id, payment_date, amount, square_payment_id
    FROM payments
    WHERE (reserve_number IS NULL OR reserve_number = '')
    AND charter_id IS NULL
    AND square_payment_id IS NOT NULL
    ORDER BY amount
""")
orphans = cur.fetchall()
print(f'\nOrphan payments: {len(orphans)} | ${sum(float(row[2]) for row in orphans):,.2f}')

# Get cancelled charters with payments (retainers)
cur.execute("""
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.client_id,
        cl.client_name,
        cl.company_name,
        c.total_amount_due,
        c.paid_amount,
        c.charter_date,
        c.status,
        cl.balance as client_balance
    FROM charters c
    INNER JOIN clients cl ON c.client_id = cl.client_id
    WHERE c.cancelled = true
    AND c.paid_amount > 0
    ORDER BY c.charter_id DESC
""")
cancelled_with_retainers = cur.fetchall()
print(f'\nCancelled charters with paid_amount > 0: {len(cancelled_with_retainers)}')

# Display cancelled charters
print(f'\nCancelled charters (retainers):')
for cid, reserve, client_id, client_name, company, total, paid, ch_date, status, cl_bal in cancelled_with_retainers:
    name = client_name or company or 'Unknown'
    bal_str = f'${cl_bal:,.2f}' if cl_bal else '$0.00'
    print(f'  Charter {cid} ({reserve}) | Client {client_id} ({name[:30]}) | Paid: ${paid:,.2f} | Client bal: {bal_str}')

# Try to match orphan payments to retainer amounts
print(f'\n' + '='*80)
print('POTENTIAL MATCHES BY AMOUNT')
print('='*80)

matches = []
for pid, pdate, amt, sq_id in orphans:
    amt_f = float(amt)
    
    # Look for cancelled charters where paid_amount matches payment
    for cid, reserve, client_id, client_name, company, total, paid, ch_date, status, cl_bal in cancelled_with_retainers:
        paid_f = float(paid)
        
        # Check if amount matches (within $1)
        if abs(amt_f - paid_f) < 1.0:
            # Check date proximity (within 60 days of charter date)
            date_diff = abs((pdate - ch_date).days) if ch_date else 999
            
            name = client_name or company or 'Unknown'
            matches.append({
                'payment_id': pid,
                'payment_date': pdate,
                'amount': amt_f,
                'charter_id': cid,
                'reserve_number': reserve,
                'client_id': client_id,
                'client_name': name,
                'retainer': paid_f,
                'client_balance': float(cl_bal) if cl_bal else 0,
                'date_diff_days': date_diff
            })

print(f'\nFound {len(matches)} potential matches')
if matches:
    # Sort by date proximity
    matches.sort(key=lambda x: x['date_diff_days'])
    
    total_matched = sum(m['amount'] for m in matches)
    print(f'Total amount: ${total_matched:,.2f}')
    
    print(f'\nMatches (sorted by date proximity):')
    for m in matches[:20]:  # Show first 20
        print(f'  Payment {m["payment_id"]} | {m["payment_date"]} | ${m["amount"]:,.2f}')
        print(f'    → Charter {m["charter_id"]} ({m["reserve_number"]}) | Client {m["client_id"]} ({m["client_name"][:40]})')
        print(f'    Retainer: ${m["retainer"]:,.2f} | Client balance: ${m["client_balance"]:,.2f} | Days diff: {m["date_diff_days"]}')
        print()
else:
    print('  (No matches found)')

# Alternative: Match by client balance
print(f'\n' + '='*80)
print('MATCHING BY CLIENT NEGATIVE BALANCE')
print('='*80)

cur.execute("""
    SELECT client_id, COALESCE(client_name, company_name) as name, balance
    FROM clients
    WHERE balance < -50
    ORDER BY balance
""")
clients_with_escrow = cur.fetchall()
print(f'\nClients with significant negative balance (retainers >$50): {len(clients_with_escrow)}')

balance_matches = []
for pid, pdate, amt, sq_id in orphans:
    amt_f = float(amt)
    
    for client_id, name, bal in clients_with_escrow:
        bal_f = float(bal)
        
        # Payment should offset negative balance
        if abs(bal_f + amt_f) < 1.0:
            balance_matches.append({
                'payment_id': pid,
                'amount': amt_f,
                'client_id': client_id,
                'client_name': name,
                'client_balance': bal_f
            })

if balance_matches:
    print(f'\nPayments matching client escrow balance: {len(balance_matches)}')
    for m in balance_matches:
        print(f'  Payment {m["payment_id"]} ${m["amount"]:,.2f} → Client {m["client_id"]} ({m["client_name"]}) | Balance: ${m["client_balance"]:,.2f}')

# Summary
print(f'\n' + '='*80)
print('SUMMARY')
print('='*80)
print(f'Orphan payments: {len(orphans)} | ${sum(float(row[2]) for row in orphans):,.2f}')
print(f'Cancelled charters with retainers: {len(cancelled_with_retainers)}')
print(f'Matched by retainer amount: {len(matches)}')
print(f'Matched by client balance: {len(balance_matches)}')

if matches or balance_matches:
    print(f'\nNEXT STEPS:')
    print(f'  1. Review matches for accuracy')
    print(f'  2. Link orphan payments to matched charters via reserve_number')
    print(f'  3. Zero out client balances after linking')
else:
    print(f'\nISSUE: Cannot match orphan payments because:')
    print(f'  - Square customer names are not populated (all NULL)')
    print(f'  - Payment amounts do not match retainer amounts')
    print(f'  - Suggest: Import Square transaction export with customer details')

cur.close()
conn.close()
