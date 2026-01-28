#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REMOVED***', host='localhost')
cur = conn.cursor()

print('='*80)
print('SEARCHING FOR: Gordon Deans')
print('='*80)

# Clients table
print('\nClients table:')
cur.execute("""
    SELECT client_id, client_name, email
    FROM clients
    WHERE client_name ILIKE %s
       OR client_name ILIKE %s
    ORDER BY client_name
""", ('%gordon%deans%', '%deans%gordon%'))

clients = cur.fetchall()
if clients:
    for c in clients:
        print(f"  Client ID: {c[0]}")
        print(f"    Name: {c[1]}")
        print(f"    Email: {c[2] or 'N/A'}")
        print()
        
        # Get charters for this client
        cur.execute("""
            SELECT reserve_number, charter_date, total_amount_due, paid_amount, balance, status
            FROM charters
            WHERE client_id = %s
            ORDER BY charter_date DESC
            LIMIT 10
        """, (c[0],))
        
        charters = cur.fetchall()
        if charters:
            print(f"    Recent charters:")
            print(f"      {'Reserve':<10} {'Date':<12} {'Due':<12} {'Paid':<12} {'Balance':<12} {'Status'}")
            for ch in charters:
                print(f"      {ch[0]:<10} {str(ch[1]):<12} ${ch[2]:<11.2f} ${ch[3]:<11.2f} ${ch[4]:<11.2f} {ch[5] or ''}")
            print()
else:
    print("  No client matches")

# Check charters directly
print('\nCharters with "Gordon" or "Deans" in client_notes or notes:')
cur.execute("""
    SELECT c.reserve_number, c.charter_date, cl.client_name, c.total_amount_due, 
           c.paid_amount, c.balance, c.notes
    FROM charters c
    LEFT JOIN clients cl ON cl.client_id = c.client_id
    WHERE c.notes ILIKE %s
       OR c.notes ILIKE %s
       OR c.client_notes ILIKE %s
       OR c.client_notes ILIKE %s
    ORDER BY c.charter_date DESC
    LIMIT 10
""", ('%gordon%', '%deans%', '%gordon%', '%deans%'))

charter_notes = cur.fetchall()
if charter_notes:
    for ch in charter_notes:
        print(f"  Reserve {ch[0]}: {ch[1]}, Client: {ch[2]}")
        print(f"    Due: ${ch[3]:.2f}, Paid: ${ch[4]:.2f}, Balance: ${ch[5]:.2f}")
        if ch[6]:
            print(f"    Notes: {ch[6]}")
        print()
else:
    print("  No matches")

# Banking transactions
print('\nBanking transactions:')
cur.execute("""
    SELECT transaction_id, transaction_date, description, 
           COALESCE(debit_amount, 0) as debit, COALESCE(credit_amount, 0) as credit,
           vendor_extracted
    FROM banking_transactions
    WHERE description ILIKE %s
       OR description ILIKE %s
       OR vendor_extracted ILIKE %s
       OR vendor_extracted ILIKE %s
    ORDER BY transaction_date DESC
    LIMIT 10
""", ('%gordon%', '%deans%', '%gordon%', '%deans%'))

banking = cur.fetchall()
if banking:
    for b in banking:
        amt = b[3] if b[3] > 0 else b[4]
        amt_type = 'debit' if b[3] > 0 else 'credit'
        print(f"  ID {b[0]}: ${amt:.2f} {amt_type} on {b[1]}")
        print(f"    Vendor: {b[5]}")
        print(f"    Desc: {b[2][:100]}")
        print()
else:
    print("  No matches")

cur.close()
conn.close()
