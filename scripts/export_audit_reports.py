import os
import csv
import psycopg2
from decimal import Decimal

DSN = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
REPORT_DIR = os.path.join(os.getcwd(), 'reports')

os.makedirs(REPORT_DIR, exist_ok=True)

def money(x):
    if x is None:
        return '0.00'
    if isinstance(x, Decimal):
        x = float(x)
    return f"{x:,.2f}"

def export_charity_runs(conn):
    sql = """
    WITH c AS (
      SELECT ch.charter_id, ch.reserve_number, ch.charter_date, ch.status,
             ch.client_id, cl.client_name, cl.email AS client_email,
             ch.rate,
             COALESCE(ch.airport_dropoff_price,0) + COALESCE(ch.airport_pickup_price,0) AS airport_fees,
             ch.beverage_service_required,
             ch.booking_notes, ch.client_notes, ch.notes
      FROM charters ch
      LEFT JOIN clients cl USING (client_id)
      WHERE COALESCE(ch.status,'') NOT IN ('cancelled','Cancelled')
    )
    , tagged AS (
      SELECT *,
        (
          (COALESCE(booking_notes,'') ~* '(charity|charitable|donation|donate|auction|silent auction|fundraiser|certificate|gift certificate|raffle|prize)') OR
          (COALESCE(client_notes,'')  ~* '(charity|charitable|donation|donate|auction|silent auction|fundraiser|certificate|gift certificate|raffle|prize)') OR
          (COALESCE(notes,'')         ~* '(charity|charitable|donation|donate|auction|silent auction|fundraiser|certificate|gift certificate|raffle|prize)') OR
          (COALESCE(client_name,'')   ~* '(foundation|charity|church|temple|mosque|synagogue|society|association|non-profit|nonprofit|school|university|college|hospital|clinic|club|rotary|lions)')
        ) AS is_charity_hint
      FROM c
    )
    , p AS (
      SELECT charter_id,
             COUNT(*) AS pay_count,
             COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) AS pay_total,
             COALESCE(SUM(CASE WHEN amount<0 THEN amount ELSE 0 END),0) AS refunds_total,
             STRING_AGG(DISTINCT COALESCE(NULLIF(LOWER(TRIM(payment_method)),''),'(null)'), '; ') AS methods
      FROM payments
      GROUP BY charter_id
    )
    SELECT t.charter_date, t.reserve_number, t.client_name, t.client_email,
           t.rate, t.airport_fees, t.beverage_service_required,
           LEFT(COALESCE(t.booking_notes,''),200) AS booking_excerpt,
           LEFT(COALESCE(t.client_notes,''),200) AS client_excerpt,
           LEFT(COALESCE(t.notes,''),200) AS notes_excerpt,
           COALESCE(p.pay_count,0) AS pay_count,
           COALESCE(p.pay_total,0) AS pay_total,
           COALESCE(p.refunds_total,0) AS refunds_total,
           COALESCE(p.methods,'') AS payment_methods
    FROM tagged t
    LEFT JOIN p USING (charter_id)
    WHERE t.is_charity_hint
    ORDER BY t.charter_date DESC;
    """
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    path = os.path.join(REPORT_DIR, 'charity_runs_suspected.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['charter_date','reserve_number','client_name','client_email','rate','airport_fees','beverage_service','booking_excerpt','client_excerpt','notes_excerpt','pay_count','pay_total','refunds_total','payment_methods'])
        for r in rows:
            r = list(r)
            r[4] = money(r[4]); r[5] = money(r[5]); r[11] = money(r[11]); r[12] = money(r[12])
            w.writerow(r)
    print(f"Wrote {len(rows)} charity runs to {path}")


def export_unmatched_deposits(conn):
    sql = """
    SELECT 
      p.payment_id, p.payment_date, p.amount,
      COALESCE(NULLIF(LOWER(TRIM(p.payment_method)),''),'(null)') AS payment_method,
      p.payment_key, p.reserve_number, p.account_number,
      p.client_id, cl.client_name, cl.email AS client_email,
      p.notes,
      (p.payment_key LIKE 'LMSDEP:%') AS is_lmsdep
    FROM payments p
    LEFT JOIN clients cl USING (client_id)
    WHERE p.reserve_number IS NULL
      AND p.amount > 0
      AND (
        p.payment_key LIKE 'LMSDEP:%' OR LOWER(COALESCE(p.payment_method,''))='deposit' OR p.notes ILIKE '%deposit%'
      )
    ORDER BY p.payment_date DESC, p.amount DESC;
    """
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    path = os.path.join(REPORT_DIR, 'unmatched_deposits.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['payment_id','payment_date','amount','payment_method','payment_key','reserve_number','account_number','client_id','client_name','client_email','notes','is_lmsdep'])
        for r in rows:
            r = list(r)
            r[2] = money(r[2])
            w.writerow(r)
    print(f"Wrote {len(rows)} unmatched deposits to {path}")


def export_unmatched_payments(conn):
    sql = """
    WITH classify AS (
      SELECT 
        p.payment_id, p.payment_date, p.amount,
        p.payment_key, p.reserve_number, p.account_number,
        p.client_id, cl.client_name, cl.email AS client_email,
        p.notes,
        COALESCE(NULLIF(LOWER(TRIM(p.payment_method)),''),'(null)') AS method_raw,
        CASE 
          WHEN p.payment_key LIKE 'LMSDEP:%' OR LOWER(COALESCE(p.payment_method,''))='deposit' OR p.notes ILIKE '%deposit%' THEN 'deposit'
          WHEN p.amount < 0 OR LOWER(COALESCE(p.payment_method,''))='refund' OR p.notes ILIKE '%refund%' THEN 'refund'
          ELSE 'payment'
        END AS nature
      FROM payments p
      LEFT JOIN clients cl USING (client_id)
      WHERE p.reserve_number IS NULL
    )
    , filtered AS (
      SELECT * FROM classify WHERE nature = 'payment' AND amount > 0
    )
    , dup AS (
      SELECT payment_date, amount, account_number, COUNT(*) AS same_group_cnt
      FROM filtered
      GROUP BY payment_date, amount, account_number
    )
    SELECT f.payment_id, f.payment_date, f.amount, f.method_raw, f.payment_key,
           f.reserve_number, f.account_number,
           f.client_id, f.client_name, f.client_email, LEFT(COALESCE(f.notes,''),200) AS notes_excerpt,
           d.same_group_cnt
    FROM filtered f
    LEFT JOIN dup d ON d.payment_date=f.payment_date AND d.amount=f.amount AND d.account_number=f.account_number
    ORDER BY f.payment_date DESC, f.amount DESC;
    """
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    path = os.path.join(REPORT_DIR, 'unmatched_payments.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['payment_id','payment_date','amount','payment_method_raw','payment_key','reserve_number','account_number','client_id','client_name','client_email','notes_excerpt','same_day_same_amount_count'])
        for r in rows:
            r = list(r)
            r[2] = money(r[2])
            w.writerow(r)
    print(f"Wrote {len(rows)} unmatched payments to {path}")


def main():
    conn = psycopg2.connect(**DSN)
    try:
        export_charity_runs(conn)
        export_unmatched_deposits(conn)
        export_unmatched_payments(conn)
    finally:
        conn.close()

if __name__ == '__main__':
    main()
