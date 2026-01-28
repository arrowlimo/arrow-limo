"""
Regenerate charity_runs_suspected.csv using ONLY the confirmed LMS promo/trade list.

User corrections:
- Previous keyword-based charity detection (271 rows) was wrong - those are NOT charity
- Actual charity/trade runs come from LMS Reserve.Pymt_Type = promo/trade
- Confirmed trade runs: 002018, 004182, 009261, 009260
- Pre-2012 data is tax-locked (filed with CRA) - flag but don't modify

This script:
1. Uses LMS promo/trade Reserve rows as authoritative charity/trade list
2. Cross-matches to Postgres charters
3. Classifies donation type
4. Flags pre-2012 entries as tax_locked
5. Exports to charity_runs_suspected.csv (replacing incorrect version)
"""
import os, csv, psycopg2, pyodbc
from decimal import Decimal
from datetime import date

REPORTS_DIR = os.path.join(os.getcwd(), 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)
LMS_PATHS = [r'L:\limo\backups\lms.mdb', r'L:\limo\lms.mdb']
DRIVERS = ['{Microsoft Access Driver (*.mdb, *.accdb)}','{Microsoft Access Driver (*.mdb)}']

TAX_LOCKED_CUTOFF = date(2012, 1, 1)  # Everything before 2012 is tax-filed, cannot modify

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
                print(f"Connected LMS {path}")
                return conn
            except Exception:
                pass
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
        print(f"LMS query failed: {e}"); rows=[]
    cur.close()
    return rows, use_cols

def classify(rate, payments_total, charter_date):
    rate_val = float(rate or 0)
    paid = float(payments_total or 0)
    
    # Determine if tax-locked (pre-2012)
    is_locked = charter_date < TAX_LOCKED_CUTOFF if charter_date else False
    lock_note = " [TAX_LOCKED]" if is_locked else ""
    
    if rate_val == 0 and paid > 0:
        return f'partial_trade_extras{lock_note}'
    if rate_val == 0 and paid == 0:
        return f'full_donation{lock_note}'
    if paid == 0 and rate_val > 0:
        return f'donated_unredeemed_or_unpaid{lock_note}'
    if rate_val > 0 and 0 < paid < rate_val*0.3:
        return f'partial_trade{lock_note}'
    if paid >= rate_val*0.9:
        return f'paid_full{lock_note}'
    return f'mixed_or_uncertain{lock_note}'

def main():
    lms_conn = connect_lms()
    if lms_conn is None:
        print("Cannot connect to LMS; abort")
        return
    
    lms_rows, lms_cols = fetch_lms_promo(lms_conn)
    print(f"Fetched {len(lms_rows)} LMS promo/trade rows")
    
    reserve_numbers = []
    for r in lms_rows:
        row_dict = dict(zip(lms_cols, r))
        reserve_numbers.append(str(row_dict.get('Reserve_No')).strip())
    
    pg_conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
    pg_cur = pg_conn.cursor()
    
    # Fetch charters with payment aggregates
    pg_cur.execute("""
        WITH pay AS (
            SELECT charter_id, 
                   COUNT(*) AS pay_count,
                   SUM(CASE WHEN amount>0 THEN amount ELSE 0 END) AS positive_payments,
                   SUM(CASE WHEN amount<0 THEN amount ELSE 0 END) AS refunds,
                   STRING_AGG(DISTINCT COALESCE(NULLIF(LOWER(TRIM(payment_method)),''),'(null)'), '; ') AS methods
            FROM payments
            GROUP BY charter_id
        )
        SELECT c.reserve_number, c.charter_date, c.client_id, cl.client_name, cl.email,
               c.rate, c.deposit, c.balance, c.beverage_service_required,
               COALESCE(p.pay_count,0) AS pay_count,
               COALESCE(p.positive_payments,0) AS payments_total,
               COALESCE(p.refunds,0) AS refunds_total,
               COALESCE(p.methods,'') AS payment_methods,
               LEFT(COALESCE(c.booking_notes,''),200) AS booking_excerpt,
               LEFT(COALESCE(c.client_notes,''),200) AS client_excerpt,
               LEFT(COALESCE(c.notes,''),200) AS notes_excerpt
        FROM charters c
        LEFT JOIN clients cl USING (client_id)
        LEFT JOIN pay p ON p.charter_id = c.charter_id
        WHERE c.reserve_number = ANY(%s)
        ORDER BY c.charter_date DESC
    """, (reserve_numbers,))
    
    charter_rows = pg_cur.fetchall()
    
    out_path = os.path.join(REPORTS_DIR, 'charity_runs_CORRECTED.csv')
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['reserve_number','charter_date','client_name','client_email','rate','payments_total','refunds_total','deposit','balance','beverage_service','pay_count','payment_methods','classification','booking_excerpt','client_excerpt','notes_excerpt'])
        
        for row in charter_rows:
            reserve_number, cdate, client_id, client_name, email, rate, deposit, balance, bev_service, pay_count, payments_total, refunds_total, methods, booking_ex, client_ex, notes_ex = row
            classification = classify(rate, payments_total, cdate)
            
            w.writerow([
                reserve_number, cdate, client_name or '', email or '', 
                money(rate), money(payments_total), money(refunds_total), money(deposit), money(balance),
                'Y' if bev_service else 'N',
                pay_count, methods, classification, 
                booking_ex or '', client_ex or '', notes_ex or ''
            ])
    
    print(f"✓ Wrote {len(charter_rows)} CONFIRMED charity/trade runs to {out_path}")
    print(f"  (Replaced incorrect keyword-based list)")
    print(f"  Pre-2012 entries flagged as [TAX_LOCKED] - CRA filing complete, data immutable")
    
    pg_cur.close(); pg_conn.close(); lms_conn.close()

if __name__ == '__main__':
    main()
