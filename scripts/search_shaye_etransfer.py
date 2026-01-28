#!/usr/bin/env python
"""
Search CIBC banking for e-transfer to Shaye for $1,223.15 (alcohol refund).
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*100)
print('SEARCH CIBC BANKING FOR SHAYE E-TRANSFER $1,223.15')
print('='*100)

# Search for exact amount
print('\n1. Exact amount search ($1,223.15):')
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, 
           balance, vendor_extracted, category
    FROM banking_transactions
    WHERE (debit_amount = 1223.15 OR credit_amount = 1223.15)
    ORDER BY transaction_date DESC
""")
exact = cur.fetchall()

if exact:
    print(f'   Found {len(exact)} transactions:')
    for t in exact:
        amount = f'${t[3]}' if t[3] else f'${t[4]}'
        print(f'   {t[1]} - {amount} - {t[2][:60]}')
else:
    print('   No exact matches')

# Search for Shaye in description
print('\n2. Search for "Shaye" in descriptions:')
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, 
           balance, vendor_extracted, category
    FROM banking_transactions
    WHERE description ILIKE '%shaye%'
    ORDER BY transaction_date DESC
    LIMIT 20
""")
shaye = cur.fetchall()

if shaye:
    print(f'   Found {len(shaye)} transactions:')
    for t in shaye:
        amount = f'-${t[3]}' if t[3] else f'+${t[4]}'
        print(f'   {t[1]} - {amount:<12} - {t[2][:70]}')
else:
    print('   No matches for "Shaye"')

# Search for Callin (first name)
print('\n3. Search for "Callin" in descriptions:')
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, 
           balance, vendor_extracted, category
    FROM banking_transactions
    WHERE description ILIKE '%callin%'
    ORDER BY transaction_date DESC
    LIMIT 20
""")
callin = cur.fetchall()

if callin:
    print(f'   Found {len(callin)} transactions:')
    for t in callin:
        amount = f'-${t[3]}' if t[3] else f'+${t[4]}'
        print(f'   {t[1]} - {amount:<12} - {t[2][:70]}')
else:
    print('   No matches for "Callin"')

# Search for e-transfers with similar amounts (within $50)
print('\n4. E-transfers between $1,173 and $1,273:')
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, 
           balance, vendor_extracted, category
    FROM banking_transactions
    WHERE (description ILIKE '%e-transfer%' OR description ILIKE '%etransfer%' 
           OR description ILIKE '%interac%')
      AND ((debit_amount BETWEEN 1173 AND 1273) OR (credit_amount BETWEEN 1173 AND 1273))
    ORDER BY transaction_date DESC
    LIMIT 20
""")
etransfers = cur.fetchall()

if etransfers:
    print(f'   Found {len(etransfers)} transactions:')
    for t in etransfers:
        amount = f'-${t[3]}' if t[3] else f'+${t[4]}'
        print(f'   {t[1]} - {amount:<12} - {t[2][:70]}')
else:
    print('   No e-transfers in that range')

# Check charters 017822 and 017823 for Callin Shaye
print('\n5. Check Callin Shaye charters (017822, 017823):')
cur.execute("""
    SELECT c.reserve_number, c.charter_date, c.total_amount_due, c.paid_amount, 
           c.balance, c.notes
    FROM charters c
    LEFT JOIN clients cl ON cl.client_id = c.client_id
    WHERE c.reserve_number IN ('017822', '017823')
       OR cl.client_name ILIKE '%shaye%'
       OR cl.client_name ILIKE '%callin%'
    ORDER BY c.charter_date DESC
""")
charters = cur.fetchall()

if charters:
    print(f'   Found {len(charters)} charters:')
    for c in charters:
        print(f'   {c[0]} - {c[1]} - Due:${c[2]} Paid:${c[3]} Balance:${c[4]}')
        if c[5]:
            print(f'      Notes: {c[5][:80]}')
else:
    print('   No charters found')

# Search for "alcohol" or "refund" in banking
print('\n6. Search for "alcohol" or "refund" in banking:')
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, 
           balance, vendor_extracted, category
    FROM banking_transactions
    WHERE (description ILIKE '%alcohol%' OR description ILIKE '%refund%')
      AND ((debit_amount BETWEEN 1173 AND 1273) OR (credit_amount BETWEEN 1173 AND 1273))
    ORDER BY transaction_date DESC
    LIMIT 20
""")
alcohol = cur.fetchall()

if alcohol:
    print(f'   Found {len(alcohol)} transactions:')
    for t in alcohol:
        amount = f'-${t[3]}' if t[3] else f'+${t[4]}'
        print(f'   {t[1]} - {amount:<12} - {t[2][:70]}')
else:
    print('   No matches for alcohol/refund in that amount range')

cur.close()
conn.close()
print('\nDone.')
