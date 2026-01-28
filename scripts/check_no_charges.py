import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Get charters with total_amount_due but NO charge records
cur.execute("""
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.charter_date,
        c.total_amount_due,
        c.paid_amount,
        c.balance,
        c.booking_status,
        c.cancelled,
        c.status
    FROM charters c
    WHERE c.total_amount_due > 0
      AND NOT EXISTS (
          SELECT 1 FROM charter_charges cc 
          WHERE cc.charter_id = c.charter_id
      )
    ORDER BY c.total_amount_due DESC
""")

charters = cur.fetchall()

print(f"Charters with total_amount_due but NO charge records: {len(charters)}")
print(f"Total amount: ${sum(r[3] for r in charters):,.2f}\n")

print("Breakdown by booking_status:")
by_status = {}
for r in charters:
    status = r[6] or 'NULL'
    if status not in by_status:
        by_status[status] = {'count': 0, 'amount': 0}
    by_status[status]['count'] += 1
    by_status[status]['amount'] += r[3]

for status, data in sorted(by_status.items(), key=lambda x: x[1]['count'], reverse=True):
    print(f"  {status}: {data['count']} charters, ${data['amount']:,.2f}")

print("\nAll charters:")
for r in charters:
    charter_id, reserve, date, total, paid, balance, b_status, cancelled, status = r
    print(f"  {reserve}: ${total:,.2f} (paid: ${paid or 0:.2f}, balance: ${balance or 0:.2f}) - {b_status}, {status}")

cur.close()
conn.close()
