import psycopg2
c = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = c.cursor()
cur.execute("SELECT reserve_number, charter_date, rate, total_amount_due, balance FROM charters WHERE reserve_number='10409' LIMIT 1")
r = cur.fetchone()
if r:
    print(f"Reserve 10409:")
    print(f"  rate: {r[2]}")
    print(f"  total_amount_due: {r[3]}")
    print(f"  balance: {r[4]}")
    print(f"\nExcel shows $1,817.27 for this reserve")
c.close()
