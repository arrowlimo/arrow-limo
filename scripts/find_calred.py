#!/usr/bin/env python3
import psycopg2

SEARCH_NAME = 'Cal Red Technical Consulting'

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REDACTED***', host='localhost')
cur = conn.cursor()

print('='*80)
print(f'SEARCHING FOR: {SEARCH_NAME}')
print('='*80)

# Clients table
print('\nClients table:')
cur.execute("""
    SELECT client_id, client_name, primary_phone, email, address_line1, notes
    FROM clients
    WHERE client_name ILIKE %s
       OR client_name ILIKE %s
    ORDER BY client_name
""", (f'%{SEARCH_NAME}%', '%cal red%'))

clients = cur.fetchall()
if clients:
    for c in clients:
        print(f"  Client ID: {c[0]}")
        print(f"    Name: {c[1]}")
        print(f"    Phone: {c[2]}")
        print(f"    Email: {c[3]}")
        print(f"    Address: {c[4]}")
        print(f"    Notes: {c[5]}")
        print()
else:
    print("  No matches")

# Charters for this client
if clients:
    client_id = clients[0][0]
    print(f'\nCharters for client {client_id}:')
    cur.execute("""
        SELECT reserve_number, charter_date, total_amount_due, paid_amount, balance, status
        FROM charters
        WHERE client_id = %s
        ORDER BY charter_date DESC
        LIMIT 20
    """, (client_id,))
    
    charters = cur.fetchall()
    if charters:
        print(f"  {'Reserve':<10} {'Date':<12} {'Due':<12} {'Paid':<12} {'Balance':<12} {'Status':<15}")
        print('  ' + '-'*75)
        for ch in charters:
            print(f"  {ch[0]:<10} {str(ch[1]):<12} ${ch[2]:<11.2f} ${ch[3]:<11.2f} ${ch[4]:<11.2f} {ch[5] or '':<15}")
    else:
        print("  No charters found")
    
    # Payments for this client
    print(f'\nPayments for client {client_id}:')
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date, payment_method, payment_key
        FROM payments
        WHERE client_id = %s
        ORDER BY payment_date DESC
        LIMIT 20
    """, (client_id,))
    
    payments = cur.fetchall()
    if payments:
        print(f"  {'ID':<8} {'Reserve':<10} {'Amount':<12} {'Date':<12} {'Method':<15} {'Key':<20}")
        print('  ' + '-'*80)
        for p in payments:
            print(f"  {p[0]:<8} {p[1] or '':<10} ${p[2]:<11.2f} {str(p[3]):<12} {p[4] or '':<15} {p[5] or '':<20}")
    else:
        print("  No payments found")

# Banking transactions mentioning this name
print('\nBanking transactions:')
cur.execute("""
    SELECT transaction_id, transaction_date, description, 
           COALESCE(debit_amount, 0) as debit, COALESCE(credit_amount, 0) as credit
    FROM banking_transactions
    WHERE description ILIKE %s
       OR vendor_extracted ILIKE %s
    ORDER BY transaction_date DESC
    LIMIT 10
""", (f'%{SEARCH_NAME}%', f'%cal red%'))

banking = cur.fetchall()
if banking:
    for b in banking:
        amt = b[3] if b[3] > 0 else b[4]
        amt_type = 'debit' if b[3] > 0 else 'credit'
        print(f"  ID {b[0]}: ${amt:.2f} {amt_type} on {b[1]}")
        print(f"    {b[2]}")
        print()
else:
    print("  No matches")

cur.close()
conn.close()
