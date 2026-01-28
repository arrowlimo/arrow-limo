import psycopg2
conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM vendor_account_ledger WHERE account_id=28 AND entry_type=\'PAYMENT\'')
print(f'Total payment ledger entries for WCB: {cur.fetchone()[0]}')

cur.execute('SELECT ledger_id, entry_date, amount, notes, source_id FROM vendor_account_ledger WHERE account_id=28 AND entry_type=\'PAYMENT\' ORDER BY entry_date')
rows = cur.fetchall()

print(f"\n{'ID':<10} {'Date':<12} {'Amount':<12} {'Receipt ID':<12} {'Notes'[:50]}")
print('-'*120)
for r in rows:
    print(f'{r[0]:<10} {r[1]} ${r[2]:>10,.2f} {r[4]:<12} {r[3][:50] if r[3] else "N/A"}')

cur.close()
conn.close()
