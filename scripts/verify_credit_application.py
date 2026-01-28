import psycopg2

c = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = c.cursor()

# Credit ledger stats
cur.execute('SELECT COUNT(*), SUM(credit_amount), SUM(remaining_balance) FROM charter_credit_ledger')
r = cur.fetchone()
print(f'Credits created: {r[0]}')
print(f'Total credit amount: ${r[1]:,.2f}')
print(f'Available balance: ${r[2]:,.2f}')

# Overpaid charters remaining
cur.execute('SELECT COUNT(*) FROM charters WHERE paid_amount > total_amount_due')
overpaid = cur.fetchone()[0]
print(f'\nOverpaid charters remaining: {overpaid}')

# Check Waste Management example
cur.execute("""
    SELECT reserve_number, total_amount_due, paid_amount, balance
    FROM charters WHERE reserve_number = '014899'
""")
r = cur.fetchone()
print(f'\nWaste Management (014899):')
print(f'  Due: ${r[1]:.2f}, Paid: ${r[2]:.2f}, Balance: ${r[3]:.2f}')

# Check credit for 014899
cur.execute("""
    SELECT credit_id, credit_amount, remaining_balance, credit_reason
    FROM charter_credit_ledger WHERE source_reserve_number = '014899'
""")
r = cur.fetchone()
if r:
    print(f'  Credit: id={r[0]}, amount=${r[1]:.2f}, available=${r[2]:.2f}, reason={r[3]}')
