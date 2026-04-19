import csv
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

AUDIT_DIR = Path(r'l:\limo\data\audit')
files = sorted(AUDIT_DIR.glob('lease_gst_zero_dryrun_*.csv'))
if not files:
    raise SystemExit('No lease_gst_zero_dryrun_*.csv found')
latest = files[-1]

candidate_ids = []
with latest.open(newline='', encoding='utf-8') as f:
    r = csv.DictReader(f)
    for row in r:
        if str(row.get('exclude_from_auto_fix','')).strip() in {'0','False','false',''}:
            try:
                candidate_ids.append(int(row['receipt_id']))
            except Exception:
                pass

if not candidate_ids:
    raise SystemExit('No eligible receipt_ids from latest dry-run csv')

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
conn.autocommit = False
cur = conn.cursor(cursor_factory=RealDictCursor)

try:
    cur.execute(
        """
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, gst_amount
        FROM receipts
        WHERE receipt_id = ANY(%s)
          AND COALESCE(gst_amount,0)=0
          AND COALESCE(gross_amount,0)>0
        ORDER BY receipt_date, receipt_id
        """,
        (candidate_ids,),
    )
    rows = cur.fetchall()

    before_count = len(rows)
    before_gross = sum(Decimal(str(r['gross_amount'] or 0)) for r in rows)

    updates = []
    for r in rows:
        gross = Decimal(str(r['gross_amount'] or 0))
        new_gst = (gross * Decimal('0.05') / Decimal('1.05')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        updates.append((new_gst, r['receipt_id']))

    cur.executemany(
        """
        UPDATE receipts
        SET gst_amount = %s,
            updated_at = NOW()
        WHERE receipt_id = %s
          AND COALESCE(gst_amount,0)=0
        """,
        updates,
    )

    cur.execute(
        """
        SELECT COUNT(*) AS cnt, COALESCE(SUM(gross_amount),0) AS gross, COALESCE(SUM(gst_amount),0) AS gst
        FROM receipts
        WHERE receipt_id = ANY(%s)
        """,
        (candidate_ids,),
    )
    after = cur.fetchone()

    cur.execute(
        """
        SELECT EXTRACT(YEAR FROM receipt_date)::int AS yr,
               COUNT(*) AS cnt,
               COALESCE(SUM(gross_amount),0) AS gross,
               COALESCE(SUM(gst_amount),0) AS gst
        FROM receipts
        WHERE receipt_id = ANY(%s)
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY yr DESC
        """,
        (candidate_ids,),
    )
    by_year = cur.fetchall()

    cur.execute(
        """
        SELECT COALESCE(vendor_name,'(blank)') AS vendor,
               COUNT(*) AS cnt,
               COALESCE(SUM(gross_amount),0) AS gross,
               COALESCE(SUM(gst_amount),0) AS gst
        FROM receipts
        WHERE receipt_id = ANY(%s)
        GROUP BY COALESCE(vendor_name,'(blank)')
        ORDER BY gross DESC
        """,
        (candidate_ids,),
    )
    by_vendor = cur.fetchall()

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_csv = AUDIT_DIR / f'lease_gst_applied_{stamp}.csv'
    cur.execute(
        """
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, gst_amount
        FROM receipts
        WHERE receipt_id = ANY(%s)
        ORDER BY receipt_date, receipt_id
        """,
        (candidate_ids,),
    )
    final_rows = cur.fetchall()

    with out_csv.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['receipt_id','receipt_date','vendor_name','gross_amount','gst_amount'])
        for rr in final_rows:
            w.writerow([rr['receipt_id'], rr['receipt_date'], rr['vendor_name'], float(Decimal(str(rr['gross_amount'] or 0))), float(Decimal(str(rr['gst_amount'] or 0)))])

    conn.commit()

    print('LEASE_GST_APPLY_DONE')
    print(f'SOURCE_DRYRUN_CSV: {latest}')
    print(f'APPLIED_ROW_COUNT: {before_count}')
    print(f'APPLIED_GROSS_TOTAL: {before_gross}')
    print(f'POST_GST_TOTAL: {after["gst"]}')
    print(f'OUTPUT_CSV: {out_csv}')
    print('BY_YEAR:')
    for r in by_year:
        print(dict(r))
    print('BY_VENDOR_TOP:')
    for r in by_vendor[:20]:
        print(dict(r))

except Exception as e:
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()
