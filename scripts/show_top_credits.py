import psycopg2

c = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = c.cursor()

cur.execute('''
    SELECT 
        cl.credit_id,
        cl.source_reserve_number,
        cl.client_id,
        c.client_name,
        cl.credit_amount,
        cl.remaining_balance,
        cl.credit_reason,
        ch.charter_date
    FROM charter_credit_ledger cl
    LEFT JOIN clients c ON c.client_id = cl.client_id
    LEFT JOIN charters ch ON ch.charter_id = cl.source_charter_id
    ORDER BY cl.credit_amount DESC
    LIMIT 10
''')

print("Top 10 Client Credits by Amount:\n")
print(f"{'#':<3} {'Reserve':<10} {'Client':<30} {'Date':<12} {'Credit':<12} {'Reason':<25}")
print("=" * 100)

for i, (credit_id, reserve, client_id, client_name, amount, remaining, reason, charter_date) in enumerate(cur.fetchall(), 1):
    client_display = (client_name or f'ID:{client_id}')[:28]
    date_display = str(charter_date) if charter_date else 'N/A'
    print(f"{i:<3} {reserve:<10} {client_display:<30} {date_display:<12} ${amount:>10,.2f} {reason:<25}")

print()
