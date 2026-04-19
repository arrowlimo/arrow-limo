import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal

reserves = ['012144', '012237', '007504']
conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')

with conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute(
        """
        SELECT reserve_number, charter_id, charter_date, total_amount_due, balance
        FROM charters
        WHERE reserve_number = ANY(%s)
        ORDER BY reserve_number, charter_id
        """,
        (reserves,)
    )
    charters = cur.fetchall()

    cur.execute(
        """
        SELECT reserve_number, payment_id, charter_id, amount, payment_date, payment_method, payment_key, notes
        FROM payments
        WHERE reserve_number = ANY(%s)
        ORDER BY reserve_number, payment_date NULLS LAST, payment_id
        """,
        (reserves,)
    )
    payments = cur.fetchall()

    payment_ids = [row['payment_id'] for row in payments]
    if payment_ids:
        cur.execute(
            """
            SELECT id, payment_id, charter_id, client_name, charter_date, amount, payment_date, payment_method, payment_key, source
            FROM charter_payments
            WHERE payment_id = ANY(%s)
            ORDER BY payment_id, id
            """,
            (payment_ids,)
        )
        charter_payments = cur.fetchall()
    else:
        charter_payments = []

conn.close()

charters_by_reserve = {}
for row in charters:
    charters_by_reserve.setdefault(row['reserve_number'], []).append(row)

payments_by_reserve = {}
for row in payments:
    payments_by_reserve.setdefault(row['reserve_number'], []).append(row)

cp_by_payment = {}
for row in charter_payments:
    cp_by_payment.setdefault(row['payment_id'], []).append(row)

def fmt(v):
    if isinstance(v, Decimal):
        return f"{v:.2f}"
    return '' if v is None else str(v)

for reserve in reserves:
    print(f"RESERVE {reserve}")
    crows = charters_by_reserve.get(reserve, [])
    prows = payments_by_reserve.get(reserve, [])
    total_abs = sum(abs(row['amount']) for row in prows if row['amount'] is not None)
    if crows:
        for crow in crows:
            expected = None if crow['total_amount_due'] is None else crow['total_amount_due'] - total_abs
            print(f"  charter_id={fmt(crow['charter_id'])} charter_date={fmt(crow['charter_date'])} total_amount_due={fmt(crow['total_amount_due'])} balance={fmt(crow['balance'])} expected_balance={fmt(expected)}")
    else:
        print("  charter: not found")
    print("  payments:")
    if prows:
        for prow in prows:
            print(f"    payment_id={fmt(prow['payment_id'])} amount={fmt(prow['amount'])} payment_date={fmt(prow['payment_date'])} payment_method={fmt(prow['payment_method'])} payment_key={fmt(prow['payment_key'])} notes={fmt(prow['notes'])}")
            linked = cp_by_payment.get(prow['payment_id'], [])
            if linked:
                for cp in linked:
                    print(f"      charter_payment id={fmt(cp['id'])} payment_id={fmt(cp['payment_id'])} charter_id={fmt(cp['charter_id'])} client_name={fmt(cp['client_name'])} charter_date={fmt(cp['charter_date'])} amount={fmt(cp['amount'])} payment_date={fmt(cp['payment_date'])} payment_method={fmt(cp['payment_method'])} payment_key={fmt(cp['payment_key'])} source={fmt(cp['source'])}")
            else:
                print("      charter_payment: none")
    else:
        print("    none")
    print()
