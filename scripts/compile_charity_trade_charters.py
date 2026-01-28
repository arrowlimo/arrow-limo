import os, csv, psycopg2, pyodbc
from decimal import Decimal

REPORTS_DIR = os.path.join(os.getcwd(), 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)
LMS_PATHS = [r'L:\limo\backups\lms.mdb', r'L:\limo\lms.mdb']

DRIVERS = ['{Microsoft Access Driver (*.mdb, *.accdb)}','{Microsoft Access Driver (*.mdb)}']

CHARITY_KEYWORDS = ['promo','promotion','trade','donation','donate','auction','certificate','gift certificate','voucher','prize','comp','complimentary','gratis','pro bono','sponsorship']

def money(x):
    if x is None: return '0.00'
    if isinstance(x, Decimal): x=float(x)
    return f"{x:,.2f}"

def connect_lms():
    for path in LMS_PATHS:
        if not os.path.exists(path):
            continue
        for d in DRIVERS:
            try:
                conn = pyodbc.connect(f'DRIVER={d};DBQ={path};')
                print(f"Connected LMS {path} via {d}")
                return conn
            except Exception as e:
                last = e
    print("Failed LMS connection; returning None")
    return None

def fetch_lms_promo(conn):
    cur = conn.cursor()
    cols = [c.column_name for c in cur.columns(table='Reserve')]
    base_cols = ['Reserve_No','PU_Date','Rate','Balance','Deposit','Pymt_Type','Name','Notes']
    use_cols = [c for c in base_cols if c in cols]
    select = ', '.join(use_cols)
    where_parts=[]
    if 'Pymt_Type' in cols:
        where_parts.append("Pymt_Type LIKE '%promo%' OR Pymt_Type LIKE '%trade%' OR UCASE(Pymt_Type) IN ('PROMO','TRADE')")
    if 'Notes' in cols:
        where_parts.append("Notes LIKE '%promo%' OR Notes LIKE '%trade%' OR Notes LIKE '%donat%' OR Notes LIKE '%cert%' OR Notes LIKE '%auction%' OR Notes LIKE '%comp%'")
    where_clause = ' OR '.join(where_parts) or '1=0'
    sql = f"SELECT {select} FROM Reserve WHERE {where_clause} ORDER BY PU_Date DESC"
    try:
        cur.execute(sql)
        rows = cur.fetchall()
    except Exception as e:
        print("LMS query failed", e); rows=[]
    cur.close(); return rows, use_cols

def classify(rate, payments_total):
    rate_val = float(rate or 0)
    paid = float(payments_total or 0)
    if rate_val == 0 and paid > 0:
        return 'partial_trade_extras'
    if rate_val == 0 and paid == 0:
        return 'full_donation'
    if paid == 0 and rate_val > 0:
        return 'donated_unredeemed_or_unpaid'
    # If paid substantially less than rate (<30%) treat as partial trade
    if rate_val > 0 and 0 < paid < rate_val*0.3:
        return 'partial_trade'
    if paid >= rate_val*0.9:
        return 'paid_full'
    return 'mixed_or_uncertain'

def main():
    lms_conn = connect_lms()
    if lms_conn is None:
        print("Cannot produce list without LMS; abort")
        return
    lms_rows, lms_cols = fetch_lms_promo(lms_conn)
    print(f"Fetched {len(lms_rows)} LMS promo/trade candidate rows")

    # Build mapping from reserve_no -> classification base
    reserve_numbers = []
    for r in lms_rows:
        row_dict = dict(zip(lms_cols, r))
        reserve_numbers.append(str(row_dict.get('Reserve_No')).strip())

    pg_conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
    pg_cur = pg_conn.cursor()
    # Fetch matching charters + payment aggregates
    pg_cur.execute("""
        WITH pay AS (
            SELECT charter_id, SUM(CASE WHEN amount>0 THEN amount ELSE 0 END) AS positive_payments
            FROM payments
            GROUP BY charter_id
        )
        SELECT c.reserve_number, c.charter_date, c.client_id, cl.client_name, cl.email,
               c.rate, c.deposit, c.balance,
               COALESCE(p.positive_payments,0) AS payments_total,
               LEFT(COALESCE(c.booking_notes,''),200) AS booking_excerpt,
               LEFT(COALESCE(c.notes,''),200) AS notes_excerpt
        FROM charters c
        LEFT JOIN clients cl USING (client_id)
        LEFT JOIN pay p ON p.charter_id = c.charter_id
        WHERE c.reserve_number = ANY(%s)
        ORDER BY c.charter_date DESC
    """, (reserve_numbers,))
    charter_rows = pg_cur.fetchall()

    out_path = os.path.join(REPORTS_DIR, 'charity_trade_charters_classified.csv')
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['reserve_number','charter_date','client_name','client_email','rate','payments_total','deposit','balance','classification','booking_excerpt','notes_excerpt'])
        for row in charter_rows:
            reserve_number, cdate, client_id, client_name, email, rate, deposit, balance, payments_total, booking_ex, notes_ex = row
            classification = classify(rate, payments_total)
            w.writerow([
                reserve_number, cdate, client_name or '', email or '', money(rate), money(payments_total), money(deposit), money(balance), classification, booking_ex, notes_ex
            ])

    print(f"Wrote classified charity/trade charter list to {out_path}")
    pg_cur.close(); pg_conn.close(); lms_conn.close()

if __name__ == '__main__':
    main()
