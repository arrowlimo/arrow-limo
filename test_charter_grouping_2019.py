import psycopg2
from decimal import Decimal
from collections import defaultdict

# Connect to PostgreSQL
def get_conn():
    return psycopg2.connect(
        dbname="almsdata",
        user="postgres",
        password="***REMOVED***",
        host="localhost"
    )

def main():
    conn = get_conn()
    cur = conn.cursor()
    # Query all charters in 2019 with client and driver info
    cur.execute('''
         SELECT c.charter_id, c.charter_date, c.client_id,
             COALESCE(cl.client_name, cl.company_name) AS display_name,
             c.driver, c.driver_hours_1, c.driver_hours_2, c.total_amount_due, c.paid_amount
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.charter_date >= '2019-01-01' AND c.charter_date < '2020-01-01'
        ORDER BY c.charter_date
    ''')
    rows = cur.fetchall()
    # Group by year, month, client, driver
    grouped = defaultdict(list)
    for row in rows:
        charter_id, charter_date, client_id, display_name, driver, h1, h2, amt_due, paid_amt = row
        year = charter_date.year if charter_date else 'N/A'
        month = charter_date.month if charter_date else 'N/A'
        key = (year, month, display_name or 'N/A', driver or 'N/A')
        grouped[key].append({
            'charter_id': charter_id,
            'charter_date': charter_date,
            'driver_hours_1': h1,
            'driver_hours_2': h2,
            'total_amount_due': amt_due,
            'paid_amount': paid_amt
        })
    # Print report
    for (year, month, client, driver), charters in sorted(grouped.items()):
        print(f"Year: {year}  Month: {month}  Client: {client}  Driver: {driver}")
        for c in charters:
            print(f"  CharterID: {c['charter_id']}  Date: {c['charter_date']}  Hrs1: {c['driver_hours_1']}  Hrs2: {c['driver_hours_2']}  Due: {c['total_amount_due']}  Paid: {c['paid_amount']}")
        print("-"*80)
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
