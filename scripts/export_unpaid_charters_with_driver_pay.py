# Export full cross list of charters with charges but zero payments before a cutoff,
# joined to driver payroll entries by reserve_number and charter_id.
# 
# Outputs CSV and MD in reports/ with cutoff in filename.
import os
import csv
from datetime import datetime
import psycopg2
import argparse


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    )


def get_amount_col(cur):
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name='payments'
        """
    )
    cols = {r[0] for r in cur.fetchall()}
    if 'amount' in cols:
        return 'amount'
    if 'payment_amount' in cols:
        return 'payment_amount'
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cutoff', default='2025-10-01', help='YYYY-MM-DD; include charters strictly before this date')
    args = ap.parse_args()

    try:
        cutoff = datetime.strptime(args.cutoff, '%Y-%m-%d').date()
    except ValueError:
        print('Invalid --cutoff; expected YYYY-MM-DD')
        return

    conn = connect(); cur = conn.cursor()
    amount_col = get_amount_col(cur)
    if not amount_col:
        print('payments amount column not found')
        return

    query = f"""
    WITH charge_sums AS (
      SELECT reserve_number::text AS reserve_text,
             ROUND(SUM(COALESCE(amount,0))::numeric,2) AS charges_sum
      FROM charter_charges
      GROUP BY reserve_text
    ),
    payment_sums AS (
      SELECT reserve_number::text AS reserve_text,
             ROUND(SUM(COALESCE({amount_col},0))::numeric,2) AS paid_sum
      FROM payments
      WHERE reserve_number IS NOT NULL
      GROUP BY reserve_text
    ),
    unpaid AS (
      SELECT c.charter_id,
             c.reserve_number::text AS reserve_text,
             CAST(c.charter_date AS DATE) AS charter_date,
             COALESCE(cs.charges_sum,0) AS charges_sum,
             COALESCE(ps.paid_sum,0) AS paid_sum
      FROM charters c
      LEFT JOIN charge_sums cs ON cs.reserve_text = c.reserve_number::text
      LEFT JOIN payment_sums ps ON ps.reserve_text = c.reserve_number::text
      WHERE CAST(c.charter_date AS DATE) < %s
        AND COALESCE(cs.charges_sum,0) > 0
        AND COALESCE(ps.paid_sum,0) = 0
    ),
    dp_by_reserve AS (
      SELECT dp.id, dp.reserve_number::text AS dp_reserve, dp.charter_id::text AS dp_charter,
             dp.driver_id, dp.pay_date, dp.gross_pay
      FROM driver_payroll dp
      JOIN unpaid u ON u.reserve_text = dp.reserve_number::text
    ),
    dp_by_charter AS (
      SELECT dp.id, dp.reserve_number::text AS dp_reserve, dp.charter_id::text AS dp_charter,
             dp.driver_id, dp.pay_date, dp.gross_pay
      FROM driver_payroll dp
      JOIN unpaid u ON u.charter_id::text = dp.charter_id::text
    ),
    dp_matches AS (
      SELECT * FROM dp_by_reserve
      UNION
      SELECT * FROM dp_by_charter
    )
    SELECT u.reserve_text AS reserve_number,
           u.charter_id,
           u.charter_date,
           u.charges_sum,
           u.paid_sum,
           c.total_amount_due,
           c.balance,
           d.id AS dp_id,
           d.driver_id,
           d.pay_date,
           d.gross_pay
    FROM unpaid u
    LEFT JOIN charters c ON c.charter_id = u.charter_id
    LEFT JOIN dp_matches d ON (d.dp_reserve = u.reserve_text OR d.dp_charter = u.charter_id::text)
    ORDER BY u.charter_date DESC NULLS LAST, u.reserve_text, d.pay_date DESC NULLS LAST, d.id
    """

    cur.execute(query, (cutoff,))
    rows = cur.fetchall()

    reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports'))
    os.makedirs(reports_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    base = f'unpaid_with_driver_pay_before_{cutoff.isoformat()}_{ts}'
    csv_path = os.path.join(reports_dir, base + '.csv')
    md_path = os.path.join(reports_dir, base + '.md')

    headers = [
        'reserve_number','charter_id','charter_date','charges_sum','paid_sum',
        'total_amount_due','balance','dp_id','driver_id','pay_date','gross_pay'
    ]

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            w.writerow(r)

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('# Unpaid-with-charges Charters and Driver Payroll Matches\n\n')
        f.write(f'Cutoff (exclusive): {cutoff.isoformat()}\n\n')
        f.write('| ' + ' | '.join(headers) + ' |\n')
        f.write('|'+ '|'.join(['---']*len(headers)) + '|\n')
        for r in rows[:300]:  # cap markdown for readability
            f.write('| ' + ' | '.join('' if x is None else str(x) for x in r) + ' |\n')
        if len(rows) > 300:
            f.write(f"\n... and {len(rows)-300} more rows in CSV\n")

        # Summary counts computed from fetched rows
    charter_keys = set()
    dp_ids = set()
    for r in rows:
        charter_keys.add((r[0], r[1]))  # (reserve_number, charter_id)
        if r[7] is not None:
            dp_ids.add(r[7])  # dp_id

    print(f"Exported cross list: {csv_path}")
    print(f"Markdown preview: {md_path}")
    print(f"Distinct unpaid-with-charges charters: {len(charter_keys)}")
    print(f"Driver payroll entries matched: {len(dp_ids)}")

    cur.close(); conn.close()


if __name__ == '__main__':
    main()
