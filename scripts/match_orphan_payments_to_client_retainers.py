#!/usr/bin/env python3
"""
Match orphan payments to client records with retainer/escrow balances.
The retainers were recorded in client balances on Jan 8, 2026.
"""
import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print('='*80)
print('MATCHING ORPHAN PAYMENTS TO CLIENT RETAINER BALANCES')
print('='*80)

# Get orphan Square payments
cur.execute("""
    SELECT 
        p.payment_id, p.payment_date, p.amount, 
        p.square_customer_name, p.square_payment_id
    FROM payments p
    WHERE (p.reserve_number IS NULL OR p.reserve_number = '')
    AND p.charter_id IS NULL
    AND p.square_payment_id IS NOT NULL
    ORDER BY p.amount
""")
orphans = cur.fetchall()
print(f'\nTotal orphan Square payments: {len(orphans)} | ${sum(float(row[2]) for row in orphans):,.2f}')

# Get clients with negative balance (retainers/credits held)
cur.execute("""
    SELECT client_id, COALESCE(client_name, company_name) as name, balance
    FROM clients
    WHERE balance < 0
    ORDER BY balance
""")
clients_with_credit = cur.fetchall()
print(f'\nClients with negative balance (retainers held): {len(clients_with_credit)}')
if clients_with_credit:
    total_credit = sum(float(row[2]) for row in clients_with_credit)
    print(f'Total retainers held: ${abs(total_credit):,.2f}')
    print(f'\nTop clients:')
    for cid, name, bal in clients_with_credit[:10]:
        print(f'  Client {cid} | {name[:45]:45} | ${bal:,.2f}')

# Try to match orphan payments to client balances
print(f'\n' + '='*80)
print('MATCHING PAYMENTS TO CLIENT BALANCES')
print('='*80)

matches_found = []
for pid, pdate, amt, cust_name, sq_id in orphans:
    amt_f = float(amt)
    
    # Strategy 1: Match by customer name
    if cust_name:
        cur.execute("""
            SELECT client_id, COALESCE(client_name, company_name) as name, balance
            FROM clients
            WHERE (LOWER(client_name) LIKE LOWER(%s) OR LOWER(company_name) LIKE LOWER(%s))
        """, (f'%{cust_name}%', f'%{cust_name}%'))
        
        name_matches = cur.fetchall()
        for cid, name, bal in name_matches:
            if bal:
                bal_f = float(bal)
                # Check if payment equals negative balance (retainer held)
                if abs(bal_f + amt_f) < 1.0:  # Payment should offset negative balance
                    matches_found.append({
                        'payment_id': pid,
                        'payment_date': pdate,
                        'amount': amt_f,
                        'customer_name': cust_name,
                        'client_id': cid,
                        'client_name': name,
                        'client_balance': bal_f,
                        'match_type': 'name_and_balance'
                    })

# Strategy 2: Match by exact amount to negative balance
for pid, pdate, amt, cust_name, sq_id in orphans:
    amt_f = float(amt)
    if any(m['payment_id'] == pid for m in matches_found):
        continue  # Already matched
    
    cur.execute("""
        SELECT client_id, COALESCE(client_name, company_name) as name, balance
        FROM clients
        WHERE balance IS NOT NULL
        AND ABS(balance + %s) < 1.0
    """, (amt_f,))
    
    balance_matches = cur.fetchall()
    if len(balance_matches) == 1:  # Only if unique match
        cid, name, bal = balance_matches[0]
        matches_found.append({
            'payment_id': pid,
            'payment_date': pdate,
            'amount': amt_f,
            'customer_name': cust_name or 'Unknown',
            'client_id': cid,
            'client_name': name,
            'client_balance': float(bal),
            'match_type': 'balance_only'
        })

print(f'\nMatches found: {len(matches_found)}')
if matches_found:
    total_matched = sum(m['amount'] for m in matches_found)
    print(f'Total matched amount: ${total_matched:,.2f}')
    print(f'\nMatched payments (retainers):')
    for m in matches_found:
        print(f'  Payment {m["payment_id"]} | {m["payment_date"]} | ${m["amount"]:,.2f}')
        print(f'    → Client {m["client_id"]} ({m["client_name"]}) | Balance: ${m["client_balance"]:,.2f}')
        print(f'    Customer: {m["customer_name"]} | Match: {m["match_type"]}')
        
        # Check for cancelled charters
        cur.execute("""
            SELECT charter_id, reserve_number, total_amount_due, paid_amount, status
            FROM charters
            WHERE client_id = %s
            AND cancelled = true
            ORDER BY charter_id DESC
            LIMIT 3
        """, (m['client_id'],))
        
        cancelled_charters = cur.fetchall()
        if cancelled_charters:
            print(f'    Cancelled charters:')
            for cid, reserve, total, paid, status in cancelled_charters:
                print(f'      Charter {cid} ({reserve}) | Total: ${total:,.2f} | Paid: ${paid:,.2f}')
else:
    print('  (No matches found between orphan payments and client balances)')

# Summary
print(f'\n' + '='*80)
print('SUMMARY')
print('='*80)
print(f'Orphan payments: {len(orphans)} | ${sum(float(row[2]) for row in orphans):,.2f}')
print(f'Matched to client retainers: {len(matches_found)} | ${sum(m["amount"] for m in matches_found):,.2f}')
print(f'Unmatched: {len(orphans) - len(matches_found)} | ${sum(float(row[2]) for row in orphans) - sum(m["amount"] for m in matches_found):,.2f}')

if matches_found:
    print(f'\nRECOMMENDATION:')
    print(f'  - {len(matches_found)} orphan payments match client retainer balances')
    print(f'  - These should be linked to the cancelled charters for those clients')
    print(f'  - Client balance should be zeroed after linking')

cur.close()
conn.close()
